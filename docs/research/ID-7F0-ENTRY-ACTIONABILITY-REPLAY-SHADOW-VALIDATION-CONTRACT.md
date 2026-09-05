# ID-7F0 — Entry Actionability Replay / Shadow Validation Discovery + Contract Freeze

**Status: DISCOVERY COMPLETE — READY FOR OWNER / CHIEF ARCHITECT
VALIDATION-CONTRACT DECISION (2026-09-05).** Read-only discovery and
design-freeze only. Zero code, schema, repository, or workflow changes.
No replay executed, no shadow observed, no production restart/deploy,
no Validate All, no methodology change, no threshold tuning.

Owner/Chief Architect closed ID-7E.1 and ID-7E overall on 2026-09-05
(canonical EntryActionability workflow integration frozen) and
authorized this discovery to design — without implementing — how the
now-complete chain (ID-7A domain/persistence, ID-7B methodology, ID-7C
evaluator, ID-7E workflow wiring) should be proven correct under
deterministic historical replay and future real shadow observation.

---

## 1. Why this milestone exists

ID-7A–ID-7E built and wired a complete, frozen V0 methodology chain, but
never validated it against real historical or live production data —
mirroring exactly the gap ID-6E closed for `EntryQualification`. ID-7F0
exists to freeze *how* that validation must work (identity, population,
PIT reconstruction rules, equivalence fields, failure taxonomy) before
any implementation, so the eventual ID-7F harness is source-grounded
rather than invented from scratch.

---

## 2. Primary question, answered

**How does ATHENA prove the frozen V0 EntryActionability implementation
behaves correctly under (A) deterministic historical replay and (B)
future real canonical-cycle shadow observation, without look-ahead,
knowledge-time leakage, methodology changes, provider dependence,
production backfill, or currentness/write-time conflation?**

Answer, in one sentence: reuse ID-6E's own two-mode pattern exactly —
(A) a read-only, `mode=ro`/`query_only=ON` **replay** function that
reconstructs bounded historical evidence and calls the real, unmodified
`EntryActionabilityEngine` at fixed historical checkpoints, writing
results only to disposable research artifacts; and (B) a read-only
**shadow** function that, once real production rows exist, either
audits their internal integrity (ID-6E's own precedent) or —
extending that precedent by one small, source-justified step (§36–37)
— independently reconstructs the same-checkpoint evaluator result from
persisted/bounded inputs and compares it field-by-field against the
real persisted row. Both modes are strictly read-only against the
canonical database; neither ever writes to `entry_actionabilities`.

---

## 3. Existing ID-6 replay precedent (primary reference, audited at source)

`src/athena/data/id6e_replay_shadow_validation.py` (703 lines, read in
full) is the governing precedent:

- **`run_replay(...)`** (lines 114–301): iterates a fixed, deterministic
  `session_dates` × `checkpoints` grid (reused verbatim from ID-6B.1B's
  own already-selected window — "not re-selected here"); for each
  checkpoint, opens `ReadOnlyStore` (below) and:
  - selects candidates via `store.candidates_at(session_date, as_of,
    per_type=...)` — a raw SQL window-function query restricted to
    `decision_type IN ('WATCH','TRADE')`, `ts<=as_of`, one row per
    instrument (most recent at-or-before the checkpoint) — market-time
    bounded, no future rows, no live/"latest" resolution;
  - loads the **exact** Decision via `_get_decision(store,
    candidate.decision_id)` — a raw `SELECT ... WHERE decision_id=?`,
    never "latest Decision for this instrument";
  - reconstructs `SessionContext`/`IntradaySignalSet`/OR15/OR30/
    RelativeStrength/RelativeVolume/Gap from bounded candle reads
    (`store.candles(instrument_id, timeframe, day_start, as_of)` —
    same `start<=ts_open<=end` bound production itself uses) —
    identical engines, identical bounding, never re-derived formulas;
  - calls the real, unmodified `EntryQualificationEngine.evaluate()` —
    methodology is never re-implemented in the harness;
  - catches only `ValueError` (input-coherence contract errors) as a
    `HarnessDefect`, never silently folded into a methodology state;
  - appends one dict per observation to an in-memory `rows` list.
- **Output destination**: `_summarize(...)` (line 511) writes
  `id6e_observations.jsonl`, `id6e_defects.jsonl`, `id6e_summary.json`
  under a caller-supplied `output_dir` — never a write to
  `entry_qualifications`. A SHA-256 `analysis_digest` over the
  (runtime-seconds-and-artifact-path-excluded) summary is recorded for
  reproducibility auditing.
- **`ReadOnlyStore`** (`src/athena/data/id6b1_entry_qualification_baseline.py:89`):
  opens the real production DB file via `sqlite3.connect(f"file:{db_path}?mode=ro",
  uri=True)` + `PRAGMA query_only=ON` — a second, independent read-only
  connection to the same file, never `SqliteRepository`'s own writable
  connection. Every read method (`candles`, `recent_candles`, `wide_m5`,
  `d1_candle_on`, `instrument_sector`, `latest_quote_ts`) is a bounded,
  cached raw SQL query.
- **`run_shadow_audit(db_path)`** (line 605): a *separate*, narrower
  function — opens the same read-only connection, and if
  `entry_qualifications` exists and is non-empty, computes purely
  descriptive statistics over the **already-persisted** rows: state/
  finality/confirmation/methodology-version distributions, a duplicate-
  logical-identity count, a naive-`persisted_at` count, and
  `persistence_latency_seconds` (`persisted_at - as_of`) percentiles
  read directly from the raw row (bypassing domain deserialization,
  which is why it can access `persisted_at` at all — see §26).
  **Important, source-grounded finding**: this function does **not**
  independently reconstruct and compare against each persisted row — it
  only self-audits the persisted population's internal integrity
  (duplicates, invariants, distributions, latency). ID-6E's own
  "shadow" therefore means *integrity/distribution audit of real
  persisted rows*, not *reconstruction-vs-production equivalence*. ID-6E
  never needed the stronger form because `EntryQualificationEngine`
  and the corresponding `entry_qualification_stage` had no equivalent
  "was this the exact production input?" question left open by the
  time ID-6E ran — the harness's own `run_replay` mode already proved
  engine-level correctness against fixed historical checkpoints
  independently. ID-7F0's own reconstruction-vs-production concept (§9)
  is a deliberate, source-justified extension of this pattern, not
  something already proven by ID-6E itself — reported honestly rather
  than assumed.
- **Failure handling precedent**: `HarnessDefect` (`kind=
  "missing_decision"` / `"input_coherence_failure"`) is the only
  failure taxonomy ID-6E actually implemented — narrower than ID-7F0's
  requested taxonomy (§34), but a direct structural precedent for "never
  silently fold a harness-level failure into a legitimate methodology
  outcome."
- **Trajectory/episode grouping**: `_decision_episode_groups` groups by
  `(instrument_id, session_date, decision_id)` — **not** `decision_type`
  — per ID-6E.1's own correction (a DecisionType is not a Decision
  identity). Directly reusable for any future ID-7F trajectory analysis.

## 4. Other replay/backtest infrastructure (isolation reference only)

`src/athena/explosive_move/` (EMR) has its own fully isolated live-shadow
worker (`live/worker.py`), its own `db/emr.db`, and its own validation
harness (DX-5) — architecturally analogous in spirit (read-only-first,
canary-gated) but methodologically and physically unrelated (different
artifact, different schema, different database file). No EMR code,
config, or database is touched or reused by this discovery.
`src/athena/scanner/scanner.py`'s `DailyMarketScanner` and
`src/athena/runtime/workflow.py`'s `WorkflowEngine`/`WorkflowStage` are
the shared orchestration primitives ID-7E itself already reuses (not a
new find) — the natural machinery any future *natural* shadow
observation runs through, never re-implemented. No other backtest
framework (Decision/Scoring/OpeningRange-specific) exists that is more
directly relevant than the ID-6E precedent above.

---

## 5. Replay unit identity — confirmed

One replay observation = one exact `EntryQualification` identity
(`instrument_id, session_date, entry_qualification_as_of, decision_id,
entry_qualification_methodology_version`) bound to its own exact
canonical `Decision` (`decision_id, decision_type, direction, run_id,
cycle_id`) at one market-time checkpoint (`entry_qualification_as_of`),
plus the point-in-time market evidence ID-7C's evaluator requires
(completed M5, VWAP + provenance, optional OR15) — producing, via the
frozen evaluator, one `(entry_actionability_as_of,
entry_actionability_methodology_version)`-identified result. This
matches the milestone's own expected candidate exactly, confirmed from
`EntryActionability`'s own composite-key definition
(`entry_actionability_models.py:302-338`) and `EntryActionabilityEngine
._emit`'s field propagation (`entry_actionability_engine.py:449-473`).
**Never replay by instrument/date alone** — confirmed structurally
necessary, since the same instrument/session can carry multiple
Decision episodes (ID-6E.1's own trajectory-identity correction applies
identically here).

---

## 6. Replay population — frozen to WATCH/TRADE, confirmed by real data

Population = every persisted `entry_qualifications` row whose
`decision_type IN ('WATCH', 'TRADE')` — exactly ID-7E's own frozen
production invocation scope (ID-7E.1). Do not include other Decision
types (none exist as persisted EQ rows regardless — EQ persistence
itself is WATCH/TRADE-only, per `entry_qualification_stage`). Within
WATCH/TRADE, replay **every** row, not only rows that would reach
ACTIONABLE — negative (`NOT_ACTIONABLE`) and `UNKNOWN` verdicts are
essential validation evidence (§13/§14).

**Real-data population check** (read-only query against the live
`db/athena.db`, no write, no code committed): as of 2026-09-05 the real
production database holds:

| Fact | Value |
|---|---|
| `entry_qualifications` row count | 11,986 — **100% `decision_type=WATCH`** (zero TRADE) |
| `entry_qualifications.as_of` range | 2026-09-03T08:15 → 2026-09-04T15:45 |
| EQ `state` distribution | `NOT_YET` 8,443; `QUALIFIED` 1,913; `UNKNOWN` 985; `EXPIRED` 645 |
| `decisions` total | 233,418 (`TRADE` 96,985; `WATCH` 95,798; `NO_TRADE` 40,635) |
| `decisions.ts` range | 2026-07-31 → 2026-09-04 |
| `TRADE` decisions with `ts >= 2026-09-03` (EQ-persistence era) | **0** |
| `TRADE` decisions, direction breakdown | **100% LONG** (zero SHORT, across all 96,985) |
| `entry_actionabilities` table | **does not exist** in the live DB |
| `schema_version` | **17** (schema v18 — ID-7A's migration — has never been applied to this database) |

**This is a decisive, source-grounded finding, not a guess:** the real
production system has not produced a single `TRADE` Decision since
2026-08-27 — before EQ persistence (2026-09-03) even began — so **zero
real `(TRADE, EntryQualification)` pairs exist in the live database
today**, and none can exist until `DecisionEngine` naturally emits a
TRADE again. WATCH is therefore the *only* population currently
available for both replay and any near-term shadow observation. This
sharpens (does not create) the same population gap ID-7B/ID-7B.1 first
found in 2026-09-04 — now confirmed current with fresh evidence, one
day later, at a larger `n`.

---

## 7. WATCH population handling

Frozen and mandatory: every WATCH-bound EQ replay/shadow observation
must reconstruct to `NOT_ACTIONABLE` / `UPSTREAM_DECISION_NOT_TRADE`
(ADR-015's own frozen contract) with the exact bound Decision/EQ
identity. Given §6's finding, WATCH is the **primary and, for now, only
real** population — its correctness is not optional supporting evidence,
it is the entire currently-available validation population.

## 8. TRADE non-qualified population handling

Frozen: TRADE + non-QUALIFIED EQ must reconstruct to `NOT_ACTIONABLE`
/ `UPSTREAM_EQ_NOT_QUALIFIED`. Per §6, **zero real examples of this
population exist today** (zero TRADE decisions since EQ persistence
began) — this remains a structurally-defined, engine-level-tested
(ID-7C's own 58+17+10 tests) but **empirically unobserved** population
until a real TRADE decision recurs. Flagged as a population limitation,
not a defect (§43/§45 below).

## 9. UNKNOWN population handling

Both `INSUFFICIENT_EVIDENCE` and `INVALIDATION_UNAVAILABLE` are
legitimate methodology outcomes to track descriptively (state/reason
distributions, mirroring `_state_block`/`_reason_root_causes` in the
ID-6E precedent) — never tuned away, never treated as a defect class
during ID-7F.

## 10. ACTIONABLE population handling

Frozen: an ACTIONABLE reconstruction must independently reproduce
`entry_reference.price` (last completed M5 close), the VWAP-loss
`operative_invalidation.level`, exact T1/T2/RR Decimal values, and empty
`reason_codes` — engine-level exactness already proven by ID-7C's own
58 tests and ID-7E's own full-pipeline `ACTIONABLE` integration test;
ID-7F's job is proving this holds against *real* historical/production
data, not re-deriving the formulas. Per §6/§8, this population is also
currently **zero in real data** and will remain so until a real TRADE +
QUALIFIED combination occurs naturally.

---

## 11. Exact Decision source

`SqliteRepository.get_decision(decision_id: str) -> Decision | None`
(`repository.py:1024`) — already exists, exact-by-id, **no new
repository API required**. The ID-6E precedent's own `_get_decision`
raw-SQL helper exists only because its `ReadOnlyStore` deliberately
never imports the writable `SqliteRepository` (a second, independent
read-only connection to the same file) — a future ID-7F harness should
mirror that same pattern (a `ReadOnlyStore`-style raw SQL `SELECT ...
WHERE decision_id=?`, or, for a live/shadow context reading through the
normal writable connection, `repo.get_decision(eq.decision_id)`
directly) — never resolve "latest Decision for this instrument."

## 12. Exact EQ source

For replay: a raw, bounded SQL scan of the `entry_qualifications` table
restricted to `decision_type IN ('WATCH','TRADE')` (mirroring
`ReadOnlyStore`'s own raw-query convention — `SqliteRepository` itself
has no whole-table EQ enumeration method, only
`list_entry_qualifications_for_instrument_session`, which is
sufficient for shadow comparison of one already-known instrument/session
but not for a full historical population scan). For shadow: read the
exact persisted EQ the production `EntryActionability` row's own copied
identity names, via `repo.get_entry_qualification(...)` (exact-identity
lookup, already exists) — never "latest EQ."

## 13. Decision/EQ binding strategy

Confirmed: load Decision by `eq.decision_id` via `get_decision` (§11);
never pair a historical/persisted EQ with any Decision resolved by
"latest for this instrument." `EntryActionabilityEngine._validate_binding`
(already frozen, ID-7C) is itself the authoritative binding proof at
evaluation time — the replay/shadow harness does not need to duplicate
that check, only avoid feeding it a wrong pair to begin with. **No real
gap found; no new repository API required.**

## 14. Historical M5 source

Bounded read of the `candles` table: `instrument_id`, `timeframe='5m'`,
`ts_open` between the session's local-midnight (`session_day_start`)
and the replay checkpoint (`as_of`), inclusive — identical bound
`ind_stage`'s own `vwap_raw` fetch already uses in production
(`owner_validation.py`), and identical to `ReadOnlyStore.candles`'s own
`ts_open>=start AND ts_open<=end` bound. No future candle can enter
because the upper bound *is* the checkpoint itself.

## 15. M5 PIT boundary

Select via `athena.session.latest_completed_candle(bounded_candles,
Timeframe.M5, as_of=checkpoint)` — the exact same canonical helper ID-7E
itself now uses in production (`owner_validation.py`'s `ind_stage`) —
never a locally re-derived completion rule. `is_candle_completed`'s own
definition (`ts_open + 5m <= as_of`) is the single authority; reused,
not reimplemented.

## 16. Historical VWAP reconstruction

Reuse `IndicatorEngine.compute(IndicatorName.VWAP, completed_candles(bounded_series,
Timeframe.M5, as_of=checkpoint), as_of=checkpoint)` over the identical
bounded M5 series §14 fetched — the exact ID-6E precedent's own
`vwap_result` construction (`id6e_replay_shadow_validation.py:191-195`),
already proven correct for reconstruction purposes. **Do not** retrieve
a later persisted indicator value or infer VWAP from a quote — no such
persisted-indicator table exists to retrieve from in any case
(`IndicatorResult` is never persisted standalone).

## 17. VWAP provenance reconstruction

`session_vwap_as_of = selected_candle.ts_open + timedelta(minutes=5)` —
identical derivation to ID-7E's own production composition. This is
mechanical, not a new design decision.

## 18. M5/VWAP checkpoint-equivalence guarantee

Structurally guaranteed by construction (§15/§17 both derive from the
same selected candle) — identical to the guarantee ID-7E's own
production composition already relies on (confirmed live by ID-7E's own
`test_id7e_trade_qualified_full_pipeline_yields_actionable`). No
tolerance, no rounding, exact equality — `EntryActionabilityMarketEvidence
.__post_init__`'s own frozen invariant (ID-7C.1) enforces this
unconditionally regardless of replay-vs-live origin.

## 19. Historical OR15 reconstruction

Reuse `OpeningRangeEngine.assess(instrument_id, as_of=checkpoint,
session_context=reconstructed_session_context, five_min_candles=bounded_series,
calendar=calendar, tzinfo=tzinfo)` — identical to both ID-7E's own
production call and ID-6E's own replay reconstruction
(`id6e_replay_shadow_validation.py:222-225`). No OR15 methodology
change; `OpeningRangeWindow.OR15` selected from the returned per-window
mapping, exactly as production does.

## 20. OR15 PIT/coherence guarantee

Same instrument (bounded query is already instrument-scoped), same
session (`SessionContext.session_date` reconstructed from the same
bounded candles the engine itself derives it from), `as_of <= replay
checkpoint` (the OR engine's own `as_of` parameter *is* the checkpoint —
cannot exceed it). `EntryActionabilityEngine._validate_or15_coherence`
(already frozen, ID-7C.1) independently re-proves this at evaluation
time regardless of reconstruction origin — belt-and-suspenders, not a
new design need.

## 21. Replay `evaluated_at` semantics

Frozen, source-grounded verdict: inject **one fixed, timezone-aware
`evaluated_at`** per replay run (e.g. derived deterministically from
`as_of` itself, such as `as_of` plus a fixed offset, or a single frozen
constant reused for the whole run) — never `datetime.now()`, never a
claim that replay "actually happened" at that instant historically
(§30). This mirrors the codebase's own established determinism
convention (`WorkflowEngine(clock=_MonoClock())`'s injected-clock
pattern; ID-6D's own injectable `persistence_clock`). For **repeated
reconstruction of the identical historical checkpoint**, injecting the
identical fixed value both times yields full `EntryActionability`
dataclass equality (§26 — determinism contract) — the strongest,
simplest correctness check available. For **shadow equivalence**
specifically (§9/§29 below), `evaluated_at` is explicitly **excluded**
from the required-equality field set: the real production row's
`evaluated_at` is a genuine, non-reproducible wall-clock instant
(`self._persistence_clock()`, live), which a later reconstruction can
never exactly reproduce — this exclusion is not a new design invention,
it directly mirrors `repository.py`'s own existing
`_entry_actionability_payload()` function, which *already* excludes
`evaluated_at` from its own conflict-detection comparison with the
documented rationale "diagnostic wall-clock-only, never identity, never
a substitute for `evidence_as_of`."

## 22. `persisted_at` requirement verdict

**`PERSISTED_AT_NOT_REQUIRED_FOR_ID7F`.** Methodology replay/shadow
equivalence needs none of it — it is write/audit metadata only,
confirmed excluded from the `EntryActionability` domain object and from
every current repository read method (established by ID-7D/ID-7E.1
already; re-confirmed here). The one place `persisted_at` legitimately
matters is **operational** latency diagnostics (ID-6E's own
`run_shadow_audit`'s `persistence_latency_seconds` block computes
`persisted_at - as_of` percentiles by reading the raw row directly,
bypassing domain deserialization) — a real, available future use for a
future ID-7F operational-metrics slice (§27 below), never a
methodology-correctness requirement. No schema/repository/domain change
is needed or proposed to expose it.

## 23. Replay output destination

Mirror ID-6E exactly: JSONL observation/defect logs plus one summary
JSON, written under a disposable research-artifacts directory (e.g.
`artifacts/research/id7f/`, git-ignored — the same convention
`artifacts/research/em1b/` already establishes for EM-1b). **Never**
write to `entry_actionabilities`; no schema v19; no new production
table.

## 24. Production-row comparison mode (shadow)

Two genuinely distinct modes, not to be confused (per the milestone's
own §16 caution):

- **Mode A — reconstructed historical replay**: no pre-existing
  `EntryActionability` production row is required or expected (none can
  exist for any period before ID-7E is actually deployed against a
  schema-v18-migrated database — see §31). Correctness is judged by
  determinism (§26) and by the frozen invariants themselves (state/
  reason/value-object correctness per §7–10).
- **Mode B — future production shadow equivalence**: once ID-7E is
  deployed and real cycles run, read the real persisted
  `EntryActionability` row (via `get_entry_actionability`/
  `list_entry_actionabilities_for_instrument_session` — already
  sufficient, no new API) and independently reconstruct the same
  checkpoint's result using §11–20's rules, then compare field-by-field
  (§25). This is the "small adapter" extension (§36/§37) beyond what
  ID-6E's own `run_shadow_audit` already does (integrity-only).

No historical backfill is performed merely to manufacture a Mode-B
comparison target for periods before deployment — Mode A already covers
that population honestly without one.

## 25. Exact equivalence field set (shadow)

Required exact equality: `instrument_id`, `session_date`, `decision_id`,
`decision_type`, `direction`, `entry_qualification_as_of`,
`entry_qualification_methodology_version`, `entry_qualification_state`,
`entry_actionability_as_of`, `entry_actionability_methodology_version`,
`state`, `reason_codes`, `entry_reference`, `entry_location_context`,
`operative_invalidation`, `opening_range_context`, `reward`,
`evidence_as_of`, `evidence_finality`, `run_id`, `cycle_id`.
**Excluded** (diagnostic only, per §21/§22): `evaluated_at`,
`persisted_at`. This list matches the milestone's own expected set
exactly, with the `evaluated_at` exclusion justified by direct source
precedent rather than asserted.

## 26. Currentness exclusion

Confirmed and unchanged: `CURRENT`/`STALE`/`SUPERSEDED`/`SESSION_CLOSED`
(`entry_actionability_currentness.is_currently_usable`) are read-time
classifications, structurally independent of persisted methodology
truth (ID-7A0.1's own frozen dimension separation) — never part of
replay/shadow methodology-equivalence. ID-7F may validate currentness
separately, only if explicitly authorized as its own slice; out of
scope here.

## 27. Determinism contract

Frozen, minimum required checks for any future ID-7F implementation:
(1) identical inputs + identical injected `evaluated_at` →
byte-for-byte `EntryActionability` dataclass equality; (2) repeated
reconstruction of the same historical checkpoint → identical bounded
market evidence (same candle selected, same VWAP, same OR15); (3) same
Decision/EQ identity → identical `state`/`reason_codes`/value objects;
(4) the deterministic engine comparison itself requires zero repository
writes. Any observed nondeterminism is a blocker (`REPLAY_EQUIVALENCE_DEFECT`,
§34), never averaged away or explained as "close enough."

## 28. Read-only database safety

Reuse `ReadOnlyStore`'s own exact pattern (`mode=ro` + `PRAGMA
query_only=ON`) for any future replay/shadow-read code — a second,
independent connection to the same DB file, never `SqliteRepository`'s
writable connection, never a mutation. This discovery itself performed
only ad-hoc, uncommitted, read-only queries against the real
`db/athena.db` (see §6's table) using this exact pattern, confirmed
zero writes.

## 29. Market-time vs. knowledge-time limitation

Preserved, unchanged: ATHENA supports market-time, point-in-time bounded
deterministic reconstruction only — never full bitemporal knowledge-time
replay (the same limitation ADR-013 already documents for
`EntryQualification`, inherited unchanged here). Any future ID-7F report
must phrase findings as "market-time bounded deterministic
reconstruction," never "what ATHENA knew live at wall-clock X." This is
an accepted architectural limitation, not an ID-7F0 or ID-7F defect.

---

## 30. Shadow definition (frozen)

After ID-7E's code is genuinely deployed (§31) and normal canonical
cycles run naturally, "shadow validation" means: read the resulting
real `EntryActionability` row, and independently reconstruct the exact
same checkpoint's expected result from persisted/bounded historical
inputs (§11–20), then compare field-by-field (§25) — read-only,
non-blocking, zero effect on Decision/EQ/actionability production
behavior, zero second live-evaluation path in the production request
path (§31 below), zero additional provider/network call, zero
methodology override.

## 31. Shadow data source

The real, live `entry_actionabilities` table (once schema v18 is
migrated and rows exist) plus the real `decisions`/`entry_qualifications`/
`candles` tables already used for replay — all read through the exact
same `ReadOnlyStore`-style read-only connection, never the writable
production connection.

## 32. Shadow production-row observation strategy — no second live path

Confirmed, and explicitly reinforced by source inspection of
`entry_actionability_stage` (ID-7E/ID-7E.1): production already calls
`EntryActionabilityEngine.evaluate()` exactly once per in-scope
Decision, synchronously, inside the real workflow. Shadow validation
must **never** add a second live invocation of the engine inside that
same request path (no duplicate write, no parallel production
evaluator call). The correct, and only structurally safe, approach is
strictly **after-the-fact**: read the already-committed production row,
reconstruct independently offline, compare — exactly what §24 Mode B
already specifies. ID-6E's own `run_shadow_audit` already establishes
this "read-only, after-the-fact" convention (it never calls
`EntryQualificationEngine` itself, only reads persisted rows) — the
extension to reconstruction-vs-comparison (§9) preserves that same
after-the-fact, read-only boundary; it does not weaken it.

## 33. Shadow operational checks

Beyond field equivalence, a future shadow slice should also capture
(all descriptive, non-gating): one row exists for every in-scope
persisted WATCH/TRADE EQ (§35); zero `entry_actionabilities` rows exist
for any out-of-scope Decision type (already structurally guaranteed by
ID-7E.1's own early scope gate — a shadow check here is a regression
guard, not new discovery); one logical row per exact identity (no
duplicates — mirrors `run_shadow_audit`'s own `duplicate_identities`
check); zero binding-validation failures reaching the repository; zero
schema/repository errors; zero stage failures attributable specifically
to `entry_actionability` (distinguishable via
`WorkflowExecution.stage_results`'s own `stage_name`/`status` fields —
already available, no new instrumentation); state/reason/evidence-
availability distributions (mirrors `_state_block`/`_reason_root_causes`);
M5/VWAP checkpoint-coherence rate (should be 100% by construction, per
§18 — any deviation is itself a defect signal). No profitability gate
anywhere in this list.

## 34. Stage/cycle latency observability

`WorkflowExecution.stage_results` (a tuple of `StageResult`, each
carrying `stage_name`, `status`, `started_offset_seconds`,
`duration_seconds`) already records per-stage timing for every
executed stage, via the same injected clock (`_MonoClock`) every other
stage already uses (confirmed at `runtime/workflow.py:169-181`). A
future shadow/operational slice can extract the `entry_actionability`
stage's own `duration_seconds` directly from this existing structure —
**no new instrumentation, no new provider-timing framework required**
(unlike ID-7P0's own separate wall-clock `CycleTimingRecorder`, which
exists for a different purpose — orchestration-boundary latency, not
per-stage `WorkflowEngine` timing, which was already deterministic and
already recorded). No gap found here.

## 35. Failure-classification contract (frozen for future use)

- `METHODOLOGY_RESULT` — `ACTIONABLE`/`NOT_ACTIONABLE`/`UNKNOWN`, a
  legitimate frozen-methodology outcome, never a defect.
- `REPLAY_EQUIVALENCE_DEFECT` — reconstructed result differs from the
  production row on any field in §25's required set.
- `UPSTREAM_BINDING_DEFECT` — Decision/EQ/EntryActionability identities
  disagree (should be structurally unreachable given `_validate_binding`
  and the repository's own binding validators, but tracked as a
  category rather than assumed impossible).
- `PIT_EVIDENCE_DEFECT` — M5/VWAP/OR15 evidence found future-dated or
  checkpoint-mismatched during reconstruction (mirrors ID-6E's own
  `HarnessDefect` pattern, generalized).
- `PERSISTENCE_DEFECT` — a missing, duplicate, or binding-mismatched
  row detected during shadow reading (mirrors `run_shadow_audit`'s own
  `duplicate_identities`/binding checks).
- `WORKFLOW_DEFECT` — the `entry_actionability` `StageResult.status`
  itself is `FAILED` for an in-scope Decision (distinguishable from a
  legitimate methodology outcome by construction — a `FAILED` stage
  never persists any row at all, per ID-7E.1's own contract-error
  isolation test).
- `DATA_AVAILABILITY` — legitimate missing evidence yielding `UNKNOWN`/
  `INSUFFICIENT_EVIDENCE` — explicitly **not** a defect category; never
  collapsed into one.

This directly answers, and generalizes, the ID-6E `HarnessDefect`
precedent (which only distinguished `missing_decision`/
`input_coherence_failure`) into the fuller taxonomy the milestone
requests.

## 36. Production activation / deployment boundary

Two independent, both-currently-unmet preconditions were found by direct
inspection of the live database (§6), not assumed:

1. **Schema**: the real production `db/athena.db` reports
   `schema_version = 17` — ID-7A's migration to schema v18 (the
   `entry_actionabilities` table) has **never been applied** to this
   database. The table does not exist there today.
2. **Code deployment**: even once schema v18 is migrated, ID-7E's code
   (the `entry_actionability` `WorkflowStage`) becomes active only on
   the next canonical cycle *after* the running service process is
   restarted with this code — Python processes do not hot-reload
   (mirrors EM-7C's own documented precedent: "real production service
   gracefully restarted via the official `./athena-serve` wrapper").

Neither action was taken, attempted, or recommended to be taken by this
discovery. The exact future activation procedure (for the owner to
execute, not this discovery): apply the schema migration, then restart
the `athena-serve` process through its normal wrapper — the next
regularly scheduled cycle after that restart will naturally begin
producing real `EntryActionability` rows for every in-scope WATCH/TRADE
Decision, no manual trigger required.

## 37. Natural-shadow policy

Confirmed: prefer naturally occurring scheduled canonical cycles over
repeated manual "Validate All" runs, exactly as ID-7P0.2's own
after-the-fact triage found real, non-trivial anomalies specifically
traceable to owner-triggered manual/ungated runs (a distinct
`config_snapshot_id='cfg-full-validation'` run, and an `os.execv`-based
restart-recovery artifact) — manual runs are a real, demonstrated source
of confounds. No restart, deploy, or Validate All was performed by this
discovery.

## 38. Sample-sufficiency policy

**No arbitrary minimum N is invented.** The direct, already-accepted
repository precedent (ID-6E) establishes exactly the staged pattern the
milestone itself expects: a first genuine canary (ID-6E.2, 165 rows) →
one complete, naturally-occurring normal session (ID-6E's own final
audit, 6,640 rows across 28 checkpoints) → closure classification only
after that full-session evidence was in hand. ID-6E's own final
closure additionally, explicitly ruled that neither same-Decision
multi-checkpoint episodes nor TRADE observation are mandatory closure
conditions — a directly relevant precedent given §6's finding that
TRADE-bound EQ rows are currently entirely absent from real data. A
future ID-7F should adopt the identical staged pattern (canary →
one full session → owner review), and should explicitly **not** treat
"zero real TRADE+EQ observations yet" as a closure blocker, mirroring
ID-6E's own accepted reasoning.

## 39. LONG empirical scope

Unchanged from ID-7B/ID-7B.1/ID-7B.2: LONG is the only empirically
validated direction. Re-confirmed by fresh real-data evidence (§6):
100% of all 96,985 real TRADE decisions in the live database, across
its entire history, are LONG.

## 40. SHORT empirical limitation

Unchanged, re-confirmed with fresh evidence: **zero** SHORT decisions
of any kind exist anywhere in the real production database (0 of
96,985 TRADE decisions). This is a population limitation inherited from
upstream `DecisionEngine`/`EntryQualificationEngine` behavior (long-
biased v0 EQ formula, per ID-7B's own finding), not something ID-7F can
or should manufacture evidence for. `LONG_VALIDATED_SHORT_UNVALIDATED`
remains the accurate framing; no synthetic SHORT records are proposed.
Structural SHORT-path engine tests (ID-7C's own direction-symmetric
formula tests) remain exactly that — structural, not empirical — and
are explicitly not conflated with empirical validation anywhere in this
discovery.

## 41. Profitability / outcome-analysis exclusion

Confirmed: initial ID-7F replay/shadow must validate **behavioral
correctness only** (methodology-verdict/PIT/binding/determinism
correctness) — never T1/T2 hit rate, win rate, PnL, expectancy, or any
profitability claim. If forward-outcome analysis is ever wanted, that
is explicitly a separate, later, separately-authorized statistical-
validation sub-milestone (mirroring how ID-7B.1's own descriptive T1/T2
hit-rate numbers were explicitly framed as descriptive-only, never a
validation gate). Recommendation: **defer outcome/profitability
validation to a distinct future sub-milestone, only if separately
authorized** — do not fold it into ID-7F's initial scope.

---

## 42. Existing infrastructure reuse classification

**Classification: B — `SMALL_ID7F_ADAPTER_REQUIRED`.**

Evidence: ID-6E's `run_replay` mode (checkpoint iteration, `ReadOnlyStore`,
exact-Decision loading, bounded reconstruction, real-engine invocation,
disposable JSONL/JSON output) is **directly reusable, near verbatim**
for ID-7F's own replay mode — swap `EntryQualificationEngine.evaluate`
for `EntryActionabilityEngine.evaluate`, iterate persisted EQ rows
instead of raw `decisions` candidates (§6/§12), and add the four extra
composed inputs (`completed_m5_close`, `session_vwap`,
`session_vwap_as_of`, `opening_range_15`) using the exact same bounded-
read/candle-selection primitives ID-7E itself already uses in
production. ID-6E's `run_shadow_audit` mode is reusable **directly** for
integrity/distribution auditing, but requires **one small, well-defined
extension** — the reconstruction-vs-production-row comparator (§24 Mode
B, §25's field set) — that does not exist in any precedent today and
must be newly written, though its every ingredient (Decision/EQ
loading, bounded evidence reconstruction, the frozen evaluator, the
existing `get_entry_actionability` read) is already proven elsewhere.
This is a small adapter, not a new architecture (Outcome C rejected —
no evidence was found for needing a fundamentally different harness
design; Outcome A rejected — the reconstruction-vs-production
comparator genuinely does not exist yet in any form).

## 43. Small-adapter contract (definition only, not implemented)

A future ID-7F harness module (naming convention mirroring
`id6e_replay_shadow_validation.py`, e.g.
`id7f_entry_actionability_replay_shadow_validation.py`) would need,
conceptually, exactly these functions — no persistence, no provider, no
methodology, no new repository API:

- `run_replay(*, db_path, config_dir, output_dir, session_dates,
  checkpoints, ...) -> dict`: iterate persisted WATCH/TRADE EQ rows at
  fixed historical checkpoints (via `ReadOnlyStore`-style read-only
  connection), load the exact bound Decision (§11), reconstruct bounded
  M5/VWAP/OR15 evidence (§14–20), call the real
  `EntryActionabilityEngine.evaluate()` with one fixed injected
  `evaluated_at` (§21), and summarize to disposable JSONL/JSON (§23) —
  directly mirroring `run_replay`'s existing shape.
- `run_shadow_equivalence(*, db_path, config_dir, session_date_range)
  -> dict`: read real, already-persisted `EntryActionability` rows
  (via `list_entry_actionabilities_for_instrument_session` or a raw
  bounded scan), independently reconstruct each one's expected result
  using the identical §11–20 rules, compare field-by-field per §25, and
  classify any mismatch per §35's taxonomy — the one genuinely new
  piece, but built entirely from already-proven ingredients.
- `run_shadow_audit(db_path) -> dict`: reused directly, unmodified in
  spirit, from ID-6E's own precedent, adapted to the
  `entry_actionabilities` table's own columns.

## 44. Future ID-7F implementation test plan (frozen now, not implemented)

At minimum: same-checkpoint reconstruction is deterministic (repeat
twice, assert full equality); no future M5 ever selected (property
proof over the bounded read); VWAP/M5 common-checkpoint exact equality
holds for every evidence-complete reconstruction; OR15 reconstruction
is instrument/session/checkpoint-bounded; exact Decision/EQ binding is
proven (never "latest"); WATCH reconstruction matches
`NOT_ACTIONABLE`/`UPSTREAM_DECISION_NOT_TRADE` for every real WATCH row;
TRADE-non-QUALIFIED and TRADE-QUALIFIED-`UNKNOWN`/`ACTIONABLE`
equivalence tests (structural/synthetic-fixture based, since §6/§8/§10
found zero real examples of these populations today — honestly labeled
as such, not presented as real-population evidence); out-of-scope
Decision types produce zero replay/shadow rows; duplicate-logical-
identity detection; production-row-vs-reconstruction full-field
equality (§25's set); zero production DB writes anywhere in the harness
(structural/mutation-proof, mirroring every prior ID-7 milestone's own
mutation-proof convention); zero provider/network calls (source-scan
proof, mirroring ID-7E's own); currentness concepts entirely absent
from the harness (source-scan proof); LONG/SHORT empirical scope
reported honestly in every generated summary (never silently omitting
the SHORT population gap).

---

## 45. Remaining risks

- **Population scarcity**: TRADE-bound EQ/EntryActionability rows are
  currently entirely absent from real data (§6) — any future ID-7F
  replay/shadow will be WATCH-dominated (likely WATCH-only) until the
  market/`DecisionEngine` produces a TRADE decision again. This is a
  real, current, honestly-reported limitation, not a defect to fix.
- **Deployment gap**: schema v18 has never been migrated against the
  live production database, and ID-7E's code has never run against it
  — genuine shadow observation is not merely "not yet started," it is
  currently structurally impossible until both actions occur (§36).
- **SHORT population**: unchanged, zero real examples exist; any SHORT
  validation remains structural-only for the foreseeable future.

No other new architectural risk was found; all composition/PIT/binding
guarantees ID-7F would need are already established by ID-7A–ID-7E.

## 46. Recommended next milestone (recommendation only)

Once the Owner/Chief Architect reviews and accepts this contract: author
the small ID-7F0.5/ID-7F adapter described in §43, run it first in
**replay mode only** (Mode A, §24) against the real historical WATCH
population already in the database (no deployment/schema-migration
prerequisite for this mode, since it never touches `entry_actionabilities`)
to prove determinism/PIT/binding correctness on real data immediately;
defer shadow-equivalence (Mode B) until the schema migration + service
restart described in §36 have actually happened, following the same
staged canary → one full session → review pattern ID-6E already
established (§38).
