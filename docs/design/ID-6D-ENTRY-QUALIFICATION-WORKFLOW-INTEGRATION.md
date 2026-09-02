# ID-6D — Entry Qualification Workflow Integration & Provenance Resolution

**Status:** Implemented. Read for the exact contract before touching the
`entry_qualification` stage, `resolve_evidence_finality`, or the workflow
graph in `owner_validation.py`.
**Depends on:** ID-6A/ID-6B.2/ID-6B.2A (pure engine, owner-closed, frozen
methodology), ID-6C/ID-6C.1 (persistence, owner-closed).
**Does not:** change the v0 readiness methodology, add API/UI, resolve
outcome/profitability validation (ID-6E), or retrofit `DecisionEngine`.

## 1. Stage placement

`entry_qualification` is a new `WorkflowStage` in the real per-instrument
graph (`OwnerValidationPipeline._scan_eligible`'s `builder()`), declared
last with `depends_on=("decision", "intraday_analytics")` and
`produces=("entry_qualification",)`. It is the first stage to join the
previously-independent `decision` branch (scoring → confidence/risk →
decision) and `intraday_analytics` branch (session → relative_strength/
relative_volume/indicators → intraday_analytics) — Entry Qualification
structurally needs both. Since nothing depends on it, it cannot perturb the
ten pre-existing stages' relative execution order (proven against the real
Kahn topological sort, mirroring the existing ID-1/ID-2/ID-4/ID-5D
ordering-stability tests).

## 2. Candidate funnel / decision-type eligibility

The engine is called **unconditionally** for every instrument's Decision
(it already emits `OUT_OF_SCOPE` for non-WATCH/TRADE types itself, so no
special-casing is needed to invoke it safely), producing a real
`EntryQualification` object into the workflow context every time. Only the
**persistence** call (`save_entry_qualification`) is scoped to WATCH/TRADE,
per the owner's explicit instruction not to flood `entry_qualifications`
with structurally irrelevant observations for Decision types that were
never in the Entry Qualification funnel.

## 3. Current Decision source of truth

The "current canonical Decision" for a candidate is defined as **exactly
the Decision `dec_stage` just produced and persisted this same workflow
cycle** (read via the existing `box["cap"].outcome.decision` closure
capture the `decision` stage already sets — not a fresh repository query).
This is provably always the freshest possible artifact for the instrument:
`OwnerValidationPipeline` runs one synchronous, single-threaded workflow
per instrument (`DailyMarketScanner._scan_one`, called sequentially over a
sorted universe), so no concurrent writer can produce a newer Decision for
the same instrument between `dec_stage` running and `entry_qualification`
running in the same cycle. `entry_qualification`'s declared
`depends_on=("decision", ...)` guarantees the topological order enforces
this sequencing. No TTL, no age threshold, and no additional "latest
Decision" repository query were introduced — none is needed, and inventing
one would be unjustified defensive machinery per the owner's explicit
"do not invent... unless a demonstrated need exists."

## 4. Decision supersession semantics

Because §3 makes "current Decision" structurally equal to "the Decision
this cycle just produced," supersession by an *older* Decision surviving
from stale workflow context is not reachable — there is no cache or prior
Decision ever consulted. A genuinely *newer* Decision (e.g. from a
different, later cycle) is a workflow/scheduling concern outside a single
cycle's execution, deliberately not solved here — the pure engine has no
repository history access, and this stage does not add any (ID-6B.2A's own
frozen boundary, preserved unchanged). If a future ID-6D+ milestone needs
to reconcile a candidate across cycles, that is out of scope here.

## 5. Session/SignalSet source

`session_context` and `signal_set` are read directly from the workflow
context (`ctx.get("session_context")`, `ctx.get("intraday_signal_set")`) —
the exact same objects `intraday_analytics_stage` already produced this
cycle, never reconstructed. Proven by object identity in
`test_id6d_engine_receives_the_exact_same_session_context_and_signal_set`.
ID-6B.2A's input-coherence checks (`_validate_input_coherence`) remain a
defensive backstop inside the engine, never normal control flow, since
both artifacts already share the same `as_of`/`session_date` by
construction (both stages read `ctx.as_of`).

## 6. Stage input contract

`decision` (via `box["cap"]`, guaranteed set by the declared `decision`
dependency), `session_context` and `signal_set` (via `ctx`, guaranteed set
by the declared `intraday_analytics` dependency, which itself depends on
`session`). No repository reads, no provider calls, no recomputation of
VWAP/trend/RS/RVOL/SessionContext.

## 7. Stage output contract

Returns `{"entry_qualification": eq}` into the workflow context — a real
`EntryQualification` object, always (even for non-WATCH/TRADE, where it is
`OUT_OF_SCOPE` and cheap/never touches `signal_set`'s content). Not
threaded into `ScanCapture`/`DailyScanReport` — out of scope for this
milestone (no reporting/API integration).

## 8. EntryQualificationEngine invocation

`entry_qualification_engine.evaluate(decision=..., session_context=...,
signal_set=..., evidence_finality=resolve_evidence_finality(decision,
session_context))` — the default `EntryQualificationPolicy()` (frozen v0
methodology identity) is used; no per-cycle policy construction, no
thresholds/config plumbing added.

## 9. Persistence invocation

`self._repo.save_entry_qualification(eq, persisted_at=ctx.as_of)`, called
only for WATCH/TRADE Decisions (§2). Uses ID-6C/ID-6C.1's repository
contract exactly, unmodified — no direct SQL, no bypass of Decision-binding
validation.

## 10. Idempotent runtime behavior

`save_entry_qualification`'s own idempotency (ID-6C) means a
`WorkflowEngine` retry or a second identical cycle (same `as_of`/`run_id`)
is a no-op, not a stage failure — `test_id6d_rerun_with_same_run_id_is_idempotent_not_duplicated`
proves exactly one row persists after two full pipeline executions with
the same `run_id`/`as_of`.

## 11. as_of semantics

`EntryQualification.as_of` is set by the engine itself from
`session_context.as_of` (unchanged since ID-6B.2A) — never wall-clock,
scheduler-tick, or persistence time. `session_context.as_of` is itself
`ctx.as_of`, the one caller-injected clock value this whole architecture
already treats as authoritative for the cycle.

## 12. persisted_at semantics

`persisted_at=ctx.as_of` — this architecture provides exactly one injected
clock per cycle (`ctx.as_of`, supplied by whatever caller invokes
`OwnerValidationPipeline.run`/`scanner.scan`); no separate wall-clock
"execution timestamp" distinct from `as_of` exists anywhere in this stage
graph (`WorkflowEngine`'s own `clock` parameter is a **monotonic** clock
used only for stage-timing/duration measurement, not a calendar datetime
source). Reusing `ctx.as_of` avoids introducing a new clock dependency at
the orchestration boundary and avoids a naive `datetime.now()`, per
CLAUDE.md's "no hidden clock reads" principle. This means
`EntryQualification.as_of == persisted_at` in practice today — a
deliberate, honest simplification given the current single-injected-clock
architecture, not a design flaw; the schema still models them as distinct
columns for a future caller (e.g. a live scheduler with its own separate
wall clock) that legitimately has two different values to supply.

## 13. Provenance limitation report (mandatory)

**Direct readiness-evidence provenance** (source-verified against
`src/athena/ops/owner_validation.py`'s real stage bodies):

| Evidence family | Timeframe(s) read |
|---|---|
| VWAP | `Timeframe.M5` only |
| Aggregate trend (5m leg) | `Timeframe.M5` |
| Aggregate trend (15m leg) | `Timeframe.M15` |
| Relative Strength (stock/market/sector) | `Timeframe.M5` |
| Relative Volume | `Timeframe.M5` history |

All four families the frozen v0 expression consumes are M5-derived (trend
jointly with M15). No candle-level "is this bar still provisional"
provenance field exists anywhere in the domain model (`Candle` carries no
such flag) — this was confirmed by source inspection, not assumed.

**Resolution rule actually implemented**
(`src/athena/intraday/entry_qualification_provenance.py`,
`resolve_evidence_finality`): reuses the pure engine's own **public,
already-documented structural/lifecycle precondition** — `decision.decision_type
in (WATCH, TRADE)` AND `session_context.phase is SessionPhase.REGULAR` —
as the sole signal for "was direct M5-sourced evidence decisive." This is
the *outer eligibility gate* the engine itself checks before ever touching
`signal_set`, not the *inner* VWAP/trend/RS-or-RVOL tri-state formula, so
it does not duplicate the readiness methodology. It was chosen specifically
(over introspecting `eq.reason_codes`) because `evidence_finality` is a
required *input* to `evaluate()`, so it must be computable *before* the
engine runs — reason-code introspection would require running the engine
twice.

`SessionPhase.REGULAR` means the session is currently active relative to
the supplied `as_of` — the same window `live_m5_settlement_repair.py`'s
own docstring explicitly excludes from its scope ("today's still-open/
most-recent session is never in scope for this backfill"), i.e. M5 for a
`REGULAR`-phase session has not yet been through settlement repair.

**Known, reported honesty limitation:** `SessionPhase.REGULAR` is
calendar/phase-relative to whatever `as_of` the caller supplies, not to
true wall-clock "right now." In genuine live production use (the intended
runtime for this milestone), `as_of` is always the real current instant,
so `REGULAR` phase unambiguously means "today, still in progress, not yet
settled." A *historical replay* invoked with a past `as_of` mid-session
would *also* classify as `LIVE_M5_PROVISIONAL` under this rule, even if
that session's M5 has, in absolute terms, already been repaired/settled by
the time of replay. This is a deliberately **conservative** direction of
error (over-classifying as provisional, never under-classifying) — safe
under ADR-013's own stated bias, since v0 has no irreversible state a false
"provisional" label could wrongly unlock. No new provenance carrier was
added to resolve this ambiguity precisely, per the owner's explicit "do not
invent... unless a demonstrated need exists" — replay-specific finality
precision was not judged a demonstrated need for this milestone.

**Indirect (canonical Decision) provenance:** ADR-013 and ID-6B.0 already
recorded that current Decision provenance is insufficient to prove whether
a Decision was materially influenced by provisional live M5 evidence. This
milestone does not retrofit `DecisionEngine`/`DecisionTrace` to change
that (explicitly forbidden). Consequently indirect provenance can **never**
currently be positively established as "free of decisive provisional M5
dependence."

**Reachability of each `EntryEvidenceFinality` value under the current
runtime:**

- `LIVE_M5_PROVISIONAL` — **reachable**, and in fact the common case for
  any WATCH/TRADE candidate evaluated during `REGULAR` phase (confirmed by
  the real integration test:
  `test_id6d_entry_qualification_persists_bound_to_the_exact_canonical_decision`
  produces exactly this value against real seeded fixture data).
- `UNKNOWN_PROVENANCE` — **reachable**, for every `OUT_OF_SCOPE`/`EXPIRED`/
  `PRE_OPEN`-`NOT_YET` candidate (no direct evidence consulted, and
  indirect Decision provenance can never be positively established).
- `NO_DECISIVE_PROVISIONAL_M5_DEPENDENCY` — **structurally unreachable**.
  It requires positive proof that *neither* direct evidence *nor* the
  bound Decision's own indirect provenance depends on provisional M5; no
  current contract can establish the Decision side of that proof, and this
  milestone does not add one. This was explicitly anticipated by the
  owner's own instruction ("This is expected to be common initially
  because ADR-013 already documented that Decision provenance is
  insufficient") — not a defect, a faithfully reported limitation.
  `test_no_decisive_provisional_m5_dependency_is_never_returned` proves
  this exhaustively across every `DecisionType` × `SessionPhase`
  combination.

**M15 provisionality:** out of scope, deliberately not modeled. ID-6B.1A
found M15's chronic *historical* off-grid technical-debt condition, but no
ID-5B-equivalent *live-settlement* classification exists for M15 the way
it does for M5. This module does not treat M15 as equivalent to M5's
provisionality question, and does not invent one — the `EntryEvidenceFinality`
enum remains framed around M5 only, matching ADR-013's own wording exactly.

## 14. Qualification-state / finality orthogonality

Unchanged — `resolve_evidence_finality` never inspects or influences
`state`; the engine echoes whatever finality it receives through
unconditionally on every state, exactly as ID-6B.2/2A/6C established.

## 15. Missing-input behavior

Handled entirely by the existing `WorkflowEngine`'s own failure-isolation
model: if `decision` or `intraday_analytics` (or any transitive dependency)
fails, `entry_qualification`'s declared `depends_on` causes it to be
automatically `SKIPPED` — no custom handling was needed or added.

## 16. Persistence-conflict behavior

Not swallowed. A `RepositoryError` raised inside the stage (e.g. an
ID-6C.1 Decision-binding conflict) propagates up through the stage
closure; `WorkflowEngine.execute()`'s existing generic exception handling
records it as a `FAILED` `StageResult` with the exact exception type and
message, isolating the failure to this one instrument without aborting the
scan — the existing, unmodified workflow convention.

## 17. PRE_OPEN / CLOSED behavior

Not specially scheduled for. The stage simply runs whenever
`OwnerValidationPipeline` runs, whatever `SessionPhase` results — no new
scheduler cadence or synthetic invocation was added solely because the
engine supports `NOT_YET`/`EXPIRED` in those phases. Whether `PRE_OPEN` is
ever actually reached depends entirely on when the real production
scheduler happens to invoke the pipeline (unaudited here — out of scope;
this milestone is workflow *wiring* correctness, not scheduler-cadence
design).

## 18. Production-write posture

**Wired, not gated.** No feature flag was found or introduced —
none was located in the existing repository conventions for this class of
stage, and inventing one was judged unjustified speculative machinery per
the owner's explicit instruction. Once `OwnerValidationPipeline.run()`
executes in real production with real market data, `entry_qualifications`
will begin accumulating real WATCH/TRADE observations immediately. No
manual mutation of the production DB occurred during this milestone's
development — every test uses `tmp_path`; the real `db/athena.db` was not
opened or modified by any test or script this session.

## 19. Deferred validation

Outcome/profitability validation, shadow-mode promotion analysis, and
replay-based accuracy assessment are explicitly ID-6E's scope, not
attempted here.

## 20. No methodology change

The frozen v0 expression (`VWAP positive AND aggregate trend BULLISH AND
(RS support OR RVOL support)`), its tri-state semantics, state precedence,
Option C, WATCH/TRADE parity, confirmation semantics, and input-coherence
rules are all byte-for-byte unchanged — verified by the full existing
ID-6B.2/2A test suite passing unmodified (67 tests).
