# ID-7A0 — Intraday Actionability Architecture

**Status: architecture/design complete, updated by ID-7A0.1's lifecycle/
currentness and WATCH-scope corrections (2026-09-04) — ready for Owner /
Chief Architect acceptance review. Companion to
`docs/adr/ADR-015-intraday-actionability-architecture.md` (Proposed).
Zero production code, schema, workflow stage, API, or UI implemented by
this milestone.**

## 1. Purpose and scope

ID-7's discovery pass established that the existing, frozen,
Decision-embedded `TradePlan` cannot be retrofitted to consume
`EntryQualification` and that a new, separate, orthogonal artifact
(Option B) is required for layer 3 of ADR-013's four-layer taxonomy: WHEN
is an already-qualified opportunity actually actionable, with what
entry/risk evidence identity and freshness semantics? ID-7A0 freezes that
architecture boundary only — identity, lifecycle, state model,
freshness/finality semantics, timestamp model, evaluation mode,
persistence direction, replay semantics, and downstream boundaries. It
does not design entry/stop/target numeric methodology (ID-7B), does not
create a schema (ID-7D), does not wire a workflow stage (ID-7E), and does
not implement replay/shadow validation (ID-7F).

## 2. Source audit

Conducted read-only, via direct source inspection (file:line citations
below are as of this session, branch `feature/decision-improvements`).

### 2.1 `Decision` — `src/athena/domain/decision.py:115-147`

Immutable (`@dataclass(frozen=True, slots=True)`). Fields:
`decision_id, ts, run_id, cycle_id, decision_type, explanation,
instrument_id, direction, score_ref, confidence_ref, risk_ref,
gate_results, trade_plan`. `decision_id = f"decision-{instrument_id}-
{as_of.isoformat()}"` (`decision/engine.py:83`) — deterministic, not a
UUID. **No `session_date` field.** `ts` is tz-aware (enforced in
`__post_init__`). A TRADE decision must carry a `trade_plan`, a
direction, and zero failed gates (`__post_init__`, lines 138-147).

### 2.2 `TradePlan` — `src/athena/domain/decision.py:14-36`

Immutable, embedded (not a separate persisted row — persisted as a JSON
column, `repository.py:916,938`). Fields: `entry_low, entry_high,
stop_loss, targets (tuple), position_size, risk_amount, risk_reward,
valid_from, valid_until`. TRADE-only. Built in
`DecisionEngine._build_plan` (`decision/engine.py:232-266`):
`entry_low = entry_high = last_close` (D1 last close);
`stop = last_close ∓ D1_ATR × atr_stop_multiple`; `target = last_close ±
D1_ATR × atr_target_multiple`; sign flips by `direction`
(LONG/SHORT — the system is confirmed bidirectional at this layer, not
long-only); `risk_reward = atr_target_multiple / atr_stop_multiple`.
Config-driven (`config/decision.json:15-18`): `atr_stop_multiple=1.5,
atr_target_multiple=3.0` → RR=2.0, `default_units=1`,
`validity_hours=6`. Zero intraday-evidence inputs. Explicit disclaimer in
the module docstring: `position_size` is "a provisional unit, NOT a
capital-based size" (`decision/engine.py:9-11`).

### 2.3 `EntryQualification` — `src/athena/intraday/entry_qualification_models.py:128-152`

Immutable. Fields: `instrument_id, session_date, as_of, run_id, cycle_id,
decision_id, decision_type, state, evidence_finality, confirmation,
reason_codes, evidence_refs, methodology_version, config_snapshot_id,
explanation`. **No surrogate id.** States (`:22-37`): `OUT_OF_SCOPE,
UNKNOWN, NOT_YET, QUALIFIED, DISQUALIFIED_FOR_SESSION, EXPIRED`.
Provisionality carrier: `evidence_finality`
(`EntryEvidenceFinality`, `:40-52`): `UNKNOWN_PROVENANCE,
LIVE_M5_PROVISIONAL, NO_DECISIVE_PROVISIONAL_M5_DEPENDENCY`.
Confirmation (`:56-62`): `UNKNOWN, NOT_EVALUATED, NOT_CONFIRMED,
CONFIRMED_BY_POLICY`. 16 reason codes (`:66-92`).

### 2.4 `entry_qualifications` schema — `src/athena/data/store/schema.py:461-489`

```sql
CREATE TABLE entry_qualifications (
    instrument_id, session_date, as_of, decision_id REFERENCES decisions(decision_id),
    methodology_version, run_id, cycle_id, decision_type, state,
    evidence_finality, confirmation, reason_codes_json, evidence_refs_json,
    config_snapshot_id, explanation, persisted_at,
    PRIMARY KEY (instrument_id, session_date, as_of, decision_id, methodology_version)
)
```

Index `(decision_id, as_of DESC)` — required because `decision_id` is
only the 4th PK column. `decision_id` FK is one-directional (existence
only; truthful binding is enforced at the repository layer,
`_validate_entry_qualification_decision_binding`, `repository.py:93-`).

### 2.5 ID-6D workflow integration — `src/athena/ops/owner_validation.py`

`entry_qualification_stage` closure (`:1360-1414`) reads the *this-cycle*
`Decision` directly from the shared `WorkflowContext`
(`box["cap"].outcome.decision`, `:1394`) — not a repository re-query — so
no staleness/TTL check is structurally needed. Reads
`session_context`/`intraday_signal_set` from context. Calls
`resolve_evidence_finality` then `EntryQualificationEngine.evaluate`.
Persists only for `WATCH`/`TRADE` (`:1404`), via
`self._repo.save_entry_qualification(eq, persisted_at=self._persistence_clock())`
(`:1411-1413`). `persistence_clock` is an injectable constructor param
(`:85`, default `lambda: datetime.now(tz=timezone.utc)`, `:107-108`),
explicitly documented as distinct from `as_of`. Stage registration:
`WorkflowStage("entry_qualification", entry_qualification_stage,
depends_on=("decision", "intraday_analytics"),
produces=("entry_qualification",))` (`:1511-1516`).

### 2.6 Latest-row query semantics — `src/athena/data/store/repository.py`

All "latest" resolution is `ORDER BY ... DESC LIMIT` — never a
superseded-row marker. Relevant methods:
`get_decision(decision_id)` (`:934-941`, exact-id),
`query_decisions(..., sort_by="ts", sort_dir="desc", limit=...)`
(`:966-1022`, general filter — no dedicated single-instrument "latest"
method beyond this),
`list_latest_decisions_by_instrument()` (`:1024-1047`, window-function,
one row per instrument across the whole table),
`save_entry_qualification(eq, *, persisted_at)` (`:1066-1157`,
append-only + idempotent: no-op on identical payload, raises on
same-key/different-payload),
`get_entry_qualification(instrument_id, session_date, as_of, decision_id,
methodology_version)` (`:1159-1179`, exact composite key),
`latest_entry_qualification_for_decision(decision_id)` (`:1181-1196`),
`latest_entry_qualification_for_instrument_session(instrument_id,
session_date)` (`:1198-1209`),
`list_entry_qualifications_for_instrument_session(...)` (`:1211-1223`,
full oldest-first history/audit view). `decisions` table is a technical
upsert (`ON CONFLICT(decision_id) DO UPDATE`, `:918-924`), but
`decision_id`'s own determinism means successive cycles naturally
produce distinct new rows in practice.

### 2.7 Workflow topology — `src/athena/runtime/workflow.py`, `src/athena/scheduling/dry_run.py`, `src/athena/ops/scheduled_run.py`, `src/athena/ops/owner_validation.py`

`HostDueRunner.run` → `DryRunCycleOrchestrator.run_cycle` (per due
trigger) → `self._pipeline.run(trigger, as_of=as_of, ingestion=ingestion,
run_id=run_id)` (`dry_run.py:154-162`) against a `DryRunPipeline`
structural Protocol (`dry_run.py:28-38`), satisfied by
`OwnerValidationPipeline` (`owner_validation.py:74`), which drives
`_scan_eligible`'s per-instrument `WorkflowStage` graph (`:782`).
`WorkflowStage` (`workflow.py:64-77`): `name, run, depends_on=(),
produces=()`. `WorkflowDefinition` (`:80-125`) validates no duplicate
names/unknown deps and computes a deterministic Kahn topological order.
`WorkflowEngine.execute` (`:134-191`) walks the order, merges each
stage's outputs into the shared context (rejecting key collisions),
skips stages whose dependencies failed/were skipped. A new stage attaches
by declaring `depends_on` on whatever existing stage names it needs and
being named by nothing else's `depends_on` — the exact non-perturbation
property already asserted in code comments for `session` and
`entry_qualification`. `WorkflowEngine` uses its own injected
deterministic clock (`_MonoClock`, `owner_validation.py:50,856`),
distinct from ID-7P0's separate, orthogonal `CycleTimingRecorder`
observability layer (`observability/timing.py`), which wraps
`DryRunCycleOrchestrator.run_cycle` itself, not `WorkflowEngine`.

### 2.8 Timestamp conventions

`EntryQualification.as_of` = evaluation/market-time checkpoint.
`entry_qualifications.persisted_at` = durable-write instant, sourced
*only* from the injected `persistence_clock` at the workflow-stage
boundary, documented as "write/audit metadata only, never part of
identity or comparison" (`repository.py:1099-1100`). The same
market-time-only, non-bitemporal pattern recurs in
`get_latest_quote(..., as_of=None)` (`:532-571`, docstring `:543-556`)
and `list_candles_recent(..., as_of=None)` (`:2208-2251`, docstring
`:2216-2233`) — both explicitly state they bound market-time (`ts_open`)
only, and say nothing about when a row was actually persisted/known
(knowledge-time/bitemporal replay, unsupported).

### 2.9 Point-in-time candle/quote reads

`get_candles(instrument_id, timeframe, start, end)` (`:457-466`),
`earliest_candle_ts(...)` (`:468-482`),
`candles_for_instruments(...)` (`:484-512`, bulk),
`list_candles_recent(instrument_id, timeframe, *, limit=500, as_of=None)`
(`:2208-2251` — the closest genuine "point-in-time" read, filters
`ts_open<=as_of` in SQL before `ORDER BY...LIMIT`),
`get_quotes(instrument_id)` (`:524-530`, full history),
`get_latest_quote(instrument_id, *, as_of=None)` (`:532-571`).
**Confirmed:** ATHENA supports genuine market-time point-in-time replay
but not bitemporal/knowledge-time replay — stated verbatim in three
places (the two docstrings above, and ADR-013 itself, lines 173-178,
180-184, 197).

### 2.10 Existing intraday evidence artifacts

`RelativeStrengthContext` (`intraday/relative_strength_models.py`, ID-4),
`RelativeVolumeContext` (`intraday/relative_volume_models.py`, ID-5D),
`OpeningRangeEvidence` (`intraday/opening_range_models.py`, ID-3 —
explicitly "analytical evidence, NOT trade methodology: no BUY/SELL, no
entry zone, no stop/target"), `GapContext` (`intraday/gap_models.py`,
ID-5C), composed into `IntradaySignalSet` (`intraday/models.py:121`,
ID-2) and `SessionContext` (`session/models.py:117`, ID-1).

### 2.11 Support/resistance reality

DarvaX owns isolated Fibonacci/level primitives
(`darvax/primitives/levels.py`, `darvax/primitives/swings.py`).
`api/darvax_mount.py` explicitly refuses to interpret them ("Methodology
blindness is the point... Fibonacci parameters... those are DarvaX's to
own and validate," ADR-010 §8). A repository-wide search
(`support|resistance|fibonacci`, excluding `darvax/`) found no
generalized support/resistance engine anywhere else in `src/athena/`.

### 2.12 ADR-013 frozen decisions relevant to ID-7

Four-layer taxonomy (lines 37-42, quoted in ADR-015 Context). EQ "will
not promote a canonical Decision, change a Decision type, create an
entry price, create a stop, create targets, size a position, place
orders" (44-49). "A newer canonical Decision supersedes the identity and
freshness of older Entry Qualification results for the same instrument.
Older observations remain audit evidence" (126-130). Bitemporal
limitation stated explicitly (173-178, 180-184, 197). Owner-gated
milestone sequence ID-6A0→ID-6E, each requiring separate approval
(199-208) — the precedent this ADR's own Consequences section follows
for ID-7A→ID-7F.

### 2.13 ADR-014 cross-track boundary

EMR's live-shadow worker (`explosive_move/live/worker.py`) is an
isolated, config-gated, independently-scheduled daemon-thread satellite
— mounted "alongside (never through)" the canonical `CycleWorker`, with
its own DB/lock/config. It exists because `run_scan_cycle` is not itself
a per-instrument `WorkflowStage`. This is architecturally orthogonal to
ID-6/ID-7 (which live inside the per-instrument `WorkflowStage` DAG) —
confirmed no structural reason exists to reuse ADR-014's worker pattern
for ID-7.

## 3. Latency implication (from ID-7P0, not recomputed)

Median canonical cycle ≈560.6s, ≈95.7% explained by the deterministic
`(N-1)×0.334s` historical-candle pacing floor — structural, stable,
normal-path, not analytical-computation-driven. Owner accepted this
attribution (ID-7P0/ID-7P0.2 both owner-approved/closed 2026-09-04) but
declared Recommendation A ("latency compensation only") **non-binding**
on ID-7 architecture. This report treats the latency as a **measured
constraint to design against**, not a decided sufficiency verdict — see
§9.

## 4. Architecture options matrix

| Option | Freshness | Determinism | Replayability | Decision/EQ binding | Provider control | Complexity | Failure isolation | Auditability | Recommended? |
|---|---|---|---|---|---|---|---|---|---|
| **1. Canonical synchronous** | Inherits EQ's own ≈9-10min ceiling | Highest — same `WorkflowExecution` as bound Decision/EQ, zero race | Simplest — inherits `WorkflowEngine`'s existing replay semantics directly | Exact, zero-race (same-cycle, same context) | Zero new provider calls — reads only this-cycle context | Lowest — zero new infrastructure | Same as existing stage graph (per-stage skip-on-dependency-failure) | Highest — one coherent `WorkflowExecution` record | **Yes (primary)** |
| **2. Async after ingestion** | Not clearly better — EQ itself is the last synchronous stage; async can't start meaningfully earlier without a change to EQ's own timing | Weaker — needs its own trigger/event and identity-resolution step | Needs new replay-determinism proof for a non-DAG-bound evaluation | Must be *re-resolved* at trigger time — new race surface (decision churn) | Still reads persisted evidence, not live Kite — controllable | Moderate — new trigger, new idempotency design | New failure mode: partial/duplicate evaluation if trigger fires twice | Weaker unless a new persisted binding proof is added | No (not now — architecture allows revisiting) |
| **3. Event-driven market-evidence** | Best only if genuinely evidence-close-triggered | Depends entirely on new infrastructure's own guarantees | Unproven — no existing event system to inherit replay from | New identity-resolution problem, same as Option 2 | Same as Option 2 | Highest — requires building an event bus that does not exist today | Unknown — new infrastructure, no track record | Unknown | No — infra doesn't exist; out of ID-7A0 scope |
| **4. On-demand/API-time** | Freshest *data*, but non-deterministic *result* | Lowest — same "Decision" can yield different results per click | Breaks — no persisted evaluation to replay unless separately cached | Ambiguous at click time under decision churn | High temptation to add a live Kite call in the handler — explicitly prohibited | Low engine complexity, but pushes complexity into consumer/UI | Failure surfaces directly to the user request | Weak unless explicitly persisted anyway | No |
| **5. Hybrid (persisted async + on-demand freshness check)** | Best of both, if genuinely needed | As strong as its persisted half | As strong as its persisted half | Same complexity as Option 2 plus a read-path | Controllable | Highest — two evaluation paths, two consistency stories | Two failure surfaces | Strong, but redundant absent proven need | No — not now; revisit only if ID-7B proves Option 1 insufficient |

## 5. Identity proposal

`EntryActionability`'s composite identity = the entire upstream
`EntryQualification` composite key, copied verbatim (`instrument_id,
session_date, entry_qualification_as_of, decision_id,
entry_qualification_methodology_version`) **plus** its own
`entry_actionability_as_of` (a second, independent point-in-time
dimension) **plus** its own `entry_actionability_methodology_version`.
`decision_id` is carried explicitly, not merely reachable via a join —
mirroring EQ's own established denormalization precedent
(`decision_type`/`run_id`/`cycle_id` stored despite FK-only binding).
No surrogate id — none exists on EQ today, and inventing one here without
architectural need is exactly what this milestone was instructed not to
do. Full reasoning and alternatives (Options B/C) in ADR-015 §Decision
and §Alternatives.

The two-timestamp-dimension design (EQ's own `as_of` + a separate
`entry_actionability_as_of`) exists specifically so a **future** Option 2
evaluator could produce additional `EntryActionability` rows bound to the
*same* EQ observation at a *later* `entry_actionability_as_of`, without
any identity/schema redesign — deferring the freshness-mode decision
without leaving the identity model vague.

## 6. State/lifecycle proposal (corrected, ID-7A0.1)

**Three separate dimensions — must not be conflated (ID-7A0.1's central
correction):**

- **(A) Methodology state** — persisted, immutable, point-in-time: what
  the ID-7 methodology concluded *at evaluation time*, from the exact
  upstream identity bound. Three values: `UNKNOWN` (evidence not yet
  computable), `NOT_ACTIONABLE` (evaluated; bound `Decision` not `TRADE`,
  bound EQ not `QUALIFIED`, or — once ID-7B exists — layer-3 conditions
  not met; reason code always distinguishes which), `ACTIONABLE`
  (evaluated; layer-3 conditions met at this checkpoint). No
  `BUY`/`SELL`/`ENTER_NOW` command states.
- **(B) Evidence freshness/currentness** — never persisted; a **read-time
  derived value** from a conceptual `is_currently_usable(...)` query,
  requiring at minimum: methodology state permits use (`ACTIONABLE`); the
  bound `decision_id` is still the current latest `Decision` for that
  instrument (checked against `list_latest_decisions_by_instrument()`,
  not assumed); evidence age (`now − evidence_as_of`) satisfies a
  freshness policy whose numeric threshold is **explicitly deferred to
  ID-7B**; and session/current-market constraints permit use. Returns an
  illustrative, non-persisted classification (exact set left to ID-7A —
  e.g. `CURRENT`/`STALE`/`SUPERSEDED`/`SESSION_CLOSED`).
- **(C) Evidence finality/provisionality** — inherited/echoed from bound
  EQ's own `evidence_finality`, independent of both (A) and (B).

**`EXPIRED` removed from the persisted methodology state.** The original
proposal's fourth state conflated (A) and (B) — "was `ACTIONABLE`
earlier, no longer current" is a comparison against an older observation,
which an immutable, append-only, point-in-time row cannot express without
either mutation (forbidden) or a later write bound to the *old* identity
(not meaningfully different from mutation). Audited: under the selected
Option 1 (canonical-cycle synchronous) architecture, each cycle's stage
only ever binds to *that cycle's own* freshly-produced Decision/EQ — there
is no code path that revisits an older EQ identity to write a new
verdict against it, so a persisted `EXPIRED` would have no writer.
Contrast with EQ's own `EntryQualificationState.EXPIRED`
(`entry_qualification_engine.py:283-285`), which is safe precisely
because it is written fresh, every cycle, from *that cycle's own* session
context ("the trading session has closed") — dimension (A) one layer
down, never a comparison to an older row.

**Historical truth remains historical truth.** A row persisted
`ACTIONABLE` at 10:00 (dimension A) stays `ACTIONABLE` under replay/audit
at 15:00 — that is what the methodology concluded at that checkpoint. A
15:00 consumer may separately and correctly find, via
`is_currently_usable`, that the same row is no longer usable now (B).
Both statements hold simultaneously without contradiction — required for
coherent audit, replay, trajectory analysis, and future backtesting.

**Upstream-not-ready / out-of-scope policy:** Option C selected — when
the bound `Decision` is not `TRADE`, or bound EQ is
`UNKNOWN`/`NOT_YET`/`EXPIRED`, `EntryActionability` is still created, in
`NOT_ACTIONABLE`, with an explicit reason code preserving the exact
blocking condition. This is the strongest choice for explainability/replay
consistency — silence or a bare unexplained non-actionable state both
lose the "why" a future consumer or auditor would need.

**Point-in-time/non-sticky:** immutable rows, no supersession write.
"Actionable once" never implies "actionable for the session." "Latest"
(by `entry_actionability_as_of`) is a query convention; "latest currently
usable" additionally requires the full `is_currently_usable` predicate,
never a bare `state`-filter.

**WATCH vs TRADE — corrected (ID-7A0.1).** Not a forced consequence of
EQ-identity binding — binding only establishes `EntryActionability`
cannot exist *without* a bound EQ row; EQ's own scope (`WATCH`+`TRADE`)
is merely the *available upstream domain*. Tested directly against
ADR-013's WHAT/WHETHER/WHEN taxonomy: `Decision=WATCH,
EntryQualification=QUALIFIED` is a reachable, coherent state (EQ's
`QUALIFIED` is purely intraday-momentum evidence, orthogonal to whatever
structural gate kept the Decision at `WATCH`), but exposing
execution-shaped WHEN/entry/risk evidence for a `WATCH` (structurally
un-authorized) opportunity would function as ATHENA implicitly
recommending entry despite the Decision remaining `WATCH` — a real
violation of the advisory-only and WHAT/WHETHER/WHEN boundaries.
**Decision: `TRADE`-only evaluation scope.** A `WATCH`-bound EQ still
produces a row (`NOT_ACTIONABLE`, reason "bound Decision is not
TRADE-type") — never silently omitted.

## 7. Freshness model (corrected, ID-7A0.1)

Four distinct timestamps/dimensions, following the ID-6D
`persistence_clock` precedent exactly, none interchangeable:

- **`entry_actionability_as_of`** — market-time checkpoint at which the
  layer-3 (A) assertion itself is made; the artifact's own
  identity-bearing dimension, parallel to `EntryQualification.as_of`.
  Under Option 1, typically coincides with the bound cycle's own `as_of`.
- **`evidence_as_of`** — market-time of the *specific decisive evidence*
  the assertion depends on (e.g. a particular M5 candle close) — may
  equal or precede `entry_actionability_as_of`, and is the term used in
  the (B) freshness/age computation. A semantically distinct concept from
  "when was this asserted," retained because a future evaluation mode
  could decouple them.
- **`evaluated_at`** — wall-clock instant the evaluation itself ran.
  Never used as either of the above.
- **`persisted_at`** — wall-clock write time, sourced from an injectable
  clock (never inline `datetime.now()`), exactly mirroring
  `persistence_clock`. Never part of identity or the (B) predicate.

Freshness (dimension B) = `now − evidence_as_of`, computed at read time
via `is_currently_usable(...)` — never frozen as a persisted "is stale"
boolean or folded into the (A) methodology state, since staleness is
relative to when it's *asked*, not when the row was written.

## 8. Timestamp model (frozen terminology)

| Name | Meaning | Used for | Precedent |
|---|---|---|---|
| `entry_actionability_as_of` | Market-time checkpoint of the layer-3 (A) assertion | Identity | New — parallel to `EntryQualification.as_of` |
| `evidence_as_of` | Market-time of the specific decisive evidence | (B) freshness/age term | New — distinct from the assertion's own checkpoint |
| `evaluated_at` | Wall-clock evaluation instant | Diagnostics only | New |
| `persisted_at` | Wall-clock durable-write instant, injectable clock | Diagnostics only | Direct precedent: `entry_qualifications.persisted_at` / `persistence_clock` |

All timezone-aware, per the codebase's existing universal convention
(`Decision.ts`, `EntryQualification.as_of`, both enforced tz-aware in
`__post_init__`).

## 9. Evaluation-mode recommendation

**Option 1 — canonical-cycle synchronous — selected as the initial
architecture.** Full reasoning in ADR-015 §Decision/§Alternatives; see
also §4's matrix. It is the only option requiring zero new
infrastructure, zero new provider traffic, and offering the strongest
possible Decision/EQ identity determinism (same `WorkflowExecution`, no
race). It necessarily inherits EQ's own existing freshness ceiling.

This is a **separate axis** from whether that ceiling is *sufficient* for
ID-7's eventual target entry timescale — that question is explicitly
**not decided here** (§Recommendation-A reassessment below;
`A_CANNOT_BE_DECIDED_UNTIL_ID7B`). The identity model (§5) is deliberately
shaped so a future stricter-freshness mode would not require redesigning
the artifact.

## 10. Recommendation-A reassessment

**`A_CANNOT_BE_DECIDED_UNTIL_ID7B`.**

ID-7P0 measured *why* the ≈9-10 minute cycle latency exists (deterministic
historical-candle pacing) — it did not, and structurally could not,
measure *how fresh* ID-7's entry/risk evidence must be, because that
depends entirely on a not-yet-written methodology (what market
conditions the entry/risk assertion depends on, how fast those conditions
can meaningfully change, what tolerance a swing/intraday trader actually
needs). This is not indecision for its own sake: the architecture itself
is decided (§9, Option 1), and is explicitly built not to foreclose a
stricter-freshness mode later. What remains undecided is a *methodology*
question, appropriately deferred to ID-7B, not an *architecture*
question this ADR could resolve by itself.

## 11. Persistence direction (design only)

Append-only, mirroring `entry_qualifications`' shape: the copied EQ key
plus `entry_actionability_as_of`/`entry_actionability_methodology_version`
as primary key; `state`; `reason_codes`; `evidence_refs`;
`evidence_as_of`/`evaluated_at`/`persisted_at`; `config_snapshot_id`;
`explanation`; and (once ID-7B exists) nested entry/stop/target value
objects. No destructive updates. No schema created by this milestone; no
indexes chosen beyond noting the same "FK column not a PK prefix" concern
EQ's own schema already resolved would recur identically here for
`decision_id`.

## 12. Query/currentness semantics (corrected, ID-7A0.1, design only)

Extends EQ's own method family: exact composite-key lookup;
latest-for-instrument/session (`ORDER BY ... DESC LIMIT 1`, a
methodology-state/dimension-A view only); full oldest-first
history/trajectory view for audit. **"Latest currently usable" is not a
`state`-filtered query alone** (an old `ACTIONABLE` row is not usable
merely because no `EXPIRED` row exists to filter out — that state no
longer exists at all) — it requires the full `is_currently_usable(...)`
read-time predicate: methodology state `ACTIONABLE` AND bound
`decision_id` still equals `list_latest_decisions_by_instrument()`'s
current row for that instrument AND evidence age within an ID-7B-decided
threshold AND session/market constraints permit use. This is a read-time
comparison composed at query time, never a write-time guess and never a
persisted flag.

## 13. Workflow/orchestration direction (design only)

Primary: a new `WorkflowStage("entry_actionability", ...,
depends_on=("entry_qualification",), produces=("entry_actionability",))`
inside the same per-instrument DAG `OwnerValidationPipeline` already
drives — zero new orchestration infrastructure, reusing `WorkflowEngine`
exactly as `entry_qualification` itself does. Not an ADR-014-style
satellite worker (that pattern solves a structurally different,
independently-scheduled concern). If a future Option 2 evaluator is ever
authorized, it would need: (a) a deterministic trigger (e.g. "an
EntryQualification row was persisted"), (b) exact Decision/EQ identity
read directly from the persisted EQ row's own composite key — never
re-derived, (c) duplicate-evaluation prevention via the same
idempotency pattern `save_entry_qualification` already uses (no-op on
identical payload, raise on conflicting payload for the same key).

## 14. Replay semantics / limitations

Inherits ATHENA's existing, ADR-013-documented limitation exactly:
genuine market-time point-in-time replay is supported (all reads
`as_of`-bounded on the evidence's own timestamp), full bitemporal/
knowledge-time replay is not (no tracking of when a row was actually
known to the system). A future ID-7F replay/shadow milestone must state
this explicitly, exactly as ID-6E's own replay harness does for
`EntryQualification` today.

## 15. Downstream boundaries

- **ID-9 (sizing):** not absorbed. `EntryActionability` may expose
  risk-distance evidence a future sizing engine consumes, but performs no
  capital allocation — consistent with `TradePlan`'s own existing
  disclaimer that `position_size` is a provisional unit, not a
  capital-based size.
- **ID-10 (live plan supervision):** not absorbed. ID-7 answers
  WHEN/entry/risk *at evaluation time*; ID-10 later answers whether an
  already-prepared plan remains valid afterward. No trailing
  stops/ongoing supervision here.
- **ID-11 (execution quality):** not absorbed. Spread/depth/impact-cost
  may later constrain actionability, but ID-7A0 only identifies this as
  an extension seam — no new provider/depth feed, no execution-quality
  computation.
- **Advisory-only boundary:** `EntryActionability` represents evidence,
  never an order intent/command/broker instruction. No
  broker/order abstractions. No position mutation.

## 16. Unresolved methodology questions (deliberately deferred to ID-7B)

- Exact entry-zone, invalidation/stop, and target/reward numeric
  methodology (buffer %, ATR/volatility multiple, chase limit, minimum
  RR, VWAP distance, spread limit, volume threshold, resistance
  distance, time-stop, slippage %).
- The exact numeric freshness policy inside `is_currently_usable`
  (evidence-age bound, session-close interaction, Decision/EQ-replacement
  interaction) — the dimensions and query semantics are frozen (§6/§7),
  the thresholds are not.
- Whether/how T1 (~+1%) / T2 (~+1.5%) goal bands translate into any
  target/reward representation.
- Whether a structural support/resistance dependency is actually needed,
  and if so, whether `OpeningRangeEvidence` suffices or a new
  data/methodology capability must be built (recorded as an open
  dependency for ID-7B/ID-8, not resolved here).
- Whether Option 2/3/5 evaluation modes are ever warranted — gated on
  ID-7B's own freshness-tolerance findings (§10).
