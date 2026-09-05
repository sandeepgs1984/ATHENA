# ADR-015 - Intraday Actionability Architecture

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-09-04 |
| Owners | Chief Architect / Project Owner |
| Scope | Intraday Intelligence ID-7 — architecture boundary only. No implementation. |
| Approval | Owner / Chief Architect accepted 2026-09-04 (via ID-7A0.1's lifecycle/currentness and WATCH-scope corrections) |

## Context

ADR-013 froze a four-layer responsibility taxonomy for intraday decision
support:

1. **Daily/Structural** (`Decision`, `TradePlan`) — WHAT is worth
   watching/trading, evaluated once per canonical cycle.
2. **Entry Qualification** (`EntryQualification`, ID-6) — WHETHER an
   already-decided opportunity is actionable at a given intraday evidence
   checkpoint, under a frozen v0 methodology (VWAP positive AND aggregate
   trend BULLISH AND (RS support OR RVOL support)).
3. **Entry/Execution planning** — WHEN, at what entry/risk evidence, is
   the opportunity actually actionable to enter. **This layer does not
   exist yet.**
4. **Live Plan Supervision** — whether a prepared plan remains valid after
   it exists. Also does not exist yet (ID-10).

ID-6 is owner-approved/closed end-to-end (ADR-013 through ID-6E). ID-7's
own discovery pass (`docs/research/ID-7-INTRADAY-ENTRY-TRADEPLAN-DISCOVERY.md`)
found the existing `TradePlan` — embedded immutably inside `Decision`,
TRADE-only, `entry_low=entry_high=last_close`, `stop = ± D1_ATR ×
atr_stop_multiple(1.5)`, `target = ± D1_ATR × atr_target_multiple(3.0)`,
zero intraday-evidence inputs (`src/athena/decision/engine.py:232-266`,
`config/decision.json:15-18`) — cannot be retrofitted to consume
`EntryQualification` without distorting the frozen Decision boundary.
Owner accepted **Option B**: a new, separate, orthogonal intraday
actionability artifact for layer 3.

ID-7P0 then measured production reality: the canonical cycle (ingestion →
Decision → EntryQualification, one per-instrument `WorkflowStage` DAG walk
per REFRESH cycle) has a median duration of ≈560.6s, ≈95.7% explained by
the deterministic Kite historical-candle pacing floor — a structural,
stable, normal-path cost, not an analytical-computation or defect cost
(`docs/research/ID-7P0-PRODUCTION-CYCLE-LATENCY-ATTRIBUTION-REVIEW.md`,
including its ID-7P0.2 correction). Owner accepted this attribution but
explicitly ruled its own Recommendation A ("latency compensation only")
**non-binding** on ID-7 architecture — ID-7P0 measured *why* the latency
exists, not *how fresh* ID-7 evidence must be.

This ADR exists to freeze the layer-3 architecture boundary — identity,
lifecycle, freshness/finality semantics, evaluation-mode, persistence
direction, and downstream boundaries — **before any domain class,
schema, workflow stage, API, or UI is written**. It intentionally defers
all entry/stop/target numeric methodology to a later, separately
authorized ID-7B milestone.

## Decision

Introduce **`EntryActionability`** as a new, immutable, point-in-time,
non-sticky domain artifact, architecturally parallel to
`EntryQualification` but one layer downstream, answering WHEN/entry/risk
rather than WHAT/WHETHER. It is evaluated as a new `WorkflowStage`
(`entry_actionability`, `depends_on=("entry_qualification",)`) inside the
**same** per-instrument canonical `WorkflowStage` DAG that already
produces `Decision` and `EntryQualification` — i.e. **Option 1,
canonical-cycle synchronous** — reusing the existing `WorkflowEngine`,
introducing zero new orchestration infrastructure, and making zero new
provider calls (it reads only evidence already ingested/persisted this
cycle, exactly as `EntryQualification`'s own stage does).

Its identity is the **entire upstream `EntryQualification` composite key,
copied verbatim** (`instrument_id, session_date, entry_qualification_as_of,
decision_id, entry_qualification_methodology_version`), plus its own
`entry_actionability_as_of` (a second, independent point-in-time
dimension — an `EntryActionability` row is bound to one specific EQ
observation, and one EQ observation may in principle be re-evaluated for
actionability at more than one later instant) and its own
`entry_actionability_methodology_version` (distinct from EQ's own
methodology version — layer 2 and layer 3 methodologies evolve
independently). `decision_id` is carried explicitly (not merely reachable
via a join through EQ), mirroring the exact denormalization precedent EQ
itself already established (EQ stores `decision_type`/`run_id`/`cycle_id`
despite being FK-bound via `decision_id` alone) for the same
auditability/explainability reason.

No surrogate/synthetic id is introduced. `EntryQualification` itself has
none (confirmed: its persisted identity is its 5-column composite primary
key, no id column) — inventing one for `EntryActionability` alone, with
no architectural need, would be exactly the kind of surrogate ID the
authorization for this milestone forbids introducing without cause.

**WATCH/TRADE scope — corrected reasoning (ID-7A0.1):** binding through
EQ's own composite identity establishes only that `EntryActionability`
*cannot exist without* a bound EQ row — it does not, by itself, force the
evaluation scope to match EQ's own scope. EQ's own persisted scope
(`WATCH`/`TRADE`) is the **available upstream domain**, not an automatic
mandate. Resolving the actual scope requires testing the semantics
directly against ADR-013's frozen taxonomy: a `WATCH` `Decision` is
already inside the WHAT-qualified universe, and EQ's `QUALIFIED` answers
WHETHER purely from intraday momentum evidence (VWAP/trend/RS/RVOL) —
orthogonal to whatever structural gate kept the `Decision` at `WATCH`
rather than `TRADE` (`Decision.__post_init__` requires zero failed gates,
a `direction`, and a `trade_plan` for `TRADE`; `WATCH` has cleared no such
bar). So `Decision=WATCH, EntryQualification=QUALIFIED` is a reachable,
coherent state — but layer 3 is not merely "is intraday momentum
favorable," it is WHEN/entry/risk: a proposed entry zone, invalidation,
and reward zone. Surfacing those specifically execution-shaped concepts
for an opportunity the structural layer has *not* authorized as
trade-worthy would function as ATHENA implicitly recommending entry
despite `Decision` remaining `WATCH` — exactly the misreading item 9 of
the ID-7A0.1 authorization warns against, and a real violation of the
WHAT/WHETHER/WHEN separation this ADR exists to preserve. **Decision:
`EntryActionability` evaluation is scoped to `decision_type == TRADE`
only.** Its *identity* still generalizes across whatever EQ rows exist
(no code-level rejection of non-`TRADE` EQ rows is needed at the identity
layer), but the `entry_actionability` stage only ever asserts a
non-trivial `ACTIONABLE`/`NOT_ACTIONABLE` methodology verdict for a
`TRADE` `Decision`. A `WATCH`-bound EQ still produces an
`EntryActionability` row (§ "Upstream not-ready policy" below, extended
to this case) — `NOT_ACTIONABLE`, with an explicit reason code identifying
"bound Decision is not TRADE-type," never silently omitted — so a
consumer never has to guess whether the stage ran.

**Three separate dimensions (ID-7A0.1) — do not conflate:**

- **(A) Methodology state** — what the ID-7 methodology concluded *at
  evaluation time*, from the exact upstream identity it is bound to. A
  point-in-time fact, persisted, immutable, three values:
  `UNKNOWN` (entry/risk evidence not yet computable), `NOT_ACTIONABLE`
  (evaluated; bound `Decision` is not `TRADE`, bound EQ is not
  `QUALIFIED`, or — once ID-7B exists — layer-3 conditions are not met;
  reason code always distinguishes which), `ACTIONABLE` (evaluated;
  layer-3 conditions, once frozen by ID-7B, are met at this checkpoint).
  No `BUY`/`SELL`/`ENTER_NOW` or other command-shaped state — ATHENA
  remains advisory-only.
- **(B) Evidence freshness/currentness** — is a *historical* methodology
  state still usable *now*? Never persisted as a state or a mutable
  boolean; always a **read-time derived value**, computed by a conceptual
  query such as `is_currently_usable(...)`, requiring at minimum: the
  methodology state permits use (`ACTIONABLE`); the bound `decision_id`
  is still the current latest `Decision` for that instrument (compared
  against `list_latest_decisions_by_instrument()`'s present row, not
  assumed); evidence age (`now − evidence_as_of`) satisfies a freshness
  policy **whose numeric threshold ID-7B decides, not this ADR**; and
  session/current-market constraints permit use (e.g. session not
  closed). Returns a small, non-persisted classification (illustrative
  labels only — exact set left to ID-7A: `CURRENT`, `STALE`,
  `SUPERSEDED`, `SESSION_CLOSED`) — a query-time value object, not a
  schema column.
- **(C) Evidence finality/provisionality** — inherited/echoed from the
  bound EQ's own `evidence_finality` (`LIVE_M5_PROVISIONAL` etc.),
  independent of both (A) and (B). A fresh `LIVE_M5_PROVISIONAL`
  observation and an old one are not the same thing, and neither
  dimension substitutes for the other.

**`EXPIRED` is removed from the persisted methodology state (ID-7A0.1,
Option A selected).** The original draft conflated (A) and (B): it
proposed `EntryActionability.EXPIRED` to mean "was `ACTIONABLE` earlier,
no longer current" — a *comparison against an older observation*, which
cannot be expressed as an immutable, point-in-time fact without either
mutating the older row (forbidden — append-only) or requiring some later
evaluation event to write a *new* row asserting "the old one is now
stale" bound to the *old* identity, which is not mutation only in name.
Audited whether Option 1 (canonical-cycle synchronous) could ever
generate such a row: under Option 1, each cycle's `entry_actionability`
stage reads and binds to *that cycle's own, freshly-produced* `Decision`
and `EntryQualification` — there is no code path under Option 1 that ever
revisits an older EQ identity to write a new verdict against it. So a
persisted `EntryActionability.EXPIRED` would never actually be reachable
under the selected architecture; keeping it "because it sounds useful"
would freeze a state with no writer.

This is a real semantic difference from EQ's own `EntryQualificationState.EXPIRED`,
which is safe: confirmed from source
(`src/athena/intraday/entry_qualification_engine.py:283-285`), EQ's
`EXPIRED` is written when the *engine itself*, evaluating *this cycle's
own* session context, determines "the trading session has closed" — a
fresh, point-in-time methodology fact computed independently every cycle,
never a comparison against an older EQ row. It is exactly dimension (A)
one layer down, not dimension (B). No change to EQ's own `EXPIRED`
semantics is proposed or needed.

Because there is no async/event-driven evaluator authorized today (§
Evaluation mode), no scenario exists under the *currently selected*
Option 1 architecture that would ever write a persisted `EntryActionability`
staleness verdict — staleness is entirely a read-time (B) concern. If a
future Option 2 evaluator is ever authorized, it would produce an
*additional, new* `EntryActionability` row (a later `entry_actionability_as_of`
bound to the *same* EQ identity — see the identity model above), never a
mutation or a stale-marking of the earlier row; that later row's own (A)
methodology state would simply be assessed fresh, exactly as any other
`EntryActionability` evaluation. This future possibility does not, by
itself, justify persisting `EXPIRED` under Option 1 today.

**Historical truth remains historical truth.** If `A1` was persisted
`ACTIONABLE` at 10:00 (dimension A), a 15:00 replay/audit query still
returns `A1.state == ACTIONABLE` — that is what the methodology concluded
at that checkpoint, and it does not change with wall-clock time. A 15:00
*consumer* may simultaneously and correctly conclude, via `is_currently_usable(A1)`
(dimension B), that `A1` is no longer usable *now*. These are not
contradictory statements; they are two different, deliberately
independent questions. This distinction is required for coherent
audit, replay, trajectory analysis, and any future backtesting.

Three distinct timestamps are frozen, following the ID-6D `persistence_clock`
precedent exactly (`src/athena/ops/owner_validation.py:97-108`), none of
them interchangeable:

- **`entry_actionability_as_of`** — the market-time checkpoint at which
  the layer-3 (methodology-state) assertion itself is made. This is the
  artifact's own identity-bearing dimension, directly parallel to
  `EntryQualification.as_of` one layer down. Under Option 1 it typically
  coincides with the bound cycle's own `as_of` (same value EQ/`Decision`
  were evaluated at); a future Option 2 evaluator could assert it later.
- **`evidence_as_of`** — the market-time of the *specific decisive
  evidence* the assertion actually depends on (e.g. a particular M5
  candle close), which may be at or before `entry_actionability_as_of`
  but is a semantically distinct concept from it — retained because
  "when was this asserted" and "how old is the evidence behind it" are
  different questions once any future evaluation mode decouples them.
- **`evaluated_at`** — wall-clock instant the evaluation computation
  itself ran. Never used as either of the above.
- **`persisted_at`** — wall-clock write time, sourced from an injectable
  clock (never inline `datetime.now()`), mirroring `persistence_clock`
  exactly.

`evaluated_at`/`persisted_at` are explicitly never part of identity,
comparison, or the (B) currentness predicate's evidence-age term — only
`entry_actionability_as_of` (identity), the copied EQ key (identity), and
`evidence_as_of` (the (B) freshness term) are.

**Upstream not-ready policy (Option C selected, extended to the TRADE-only
scope decision above):** when the bound `Decision` is not `TRADE`, or the
bound `EntryQualification` is `UNKNOWN`, `NOT_YET`, or `EXPIRED` (EQ's own,
dimension-(A)-one-layer-down `EXPIRED` — see above), `EntryActionability`
**is still created**, in state `NOT_ACTIONABLE`, with an explicit reason
code preserving the exact blocking condition (upstream EQ state, or
"bound Decision is not TRADE-type"). Creating nothing would make "why is
there no `EntryActionability` for this Decision at this checkpoint"
ambiguous (stage skipped? EQ blocked it? scope excluded it? evaluation
error?) — exactly the kind of silent gap ATHENA's explainability
principle forbids. This mirrors EQ's own reason-code pattern
(`EntryQualificationReasonCode`) at one layer up, and keeps upstream EQ's
own `EXPIRED` state clearly separate from any notion of *this* artifact's
own staleness — they are different dimensions on different layers.

Directionality is preserved explicitly (`direction: Direction`, reusing
`Decision`'s own enum) — **not** assumed long-only.
`TradePlan._build_plan`'s existing LONG/SHORT sign-flip
(`decision/engine.py:232-266`) proves the current system is already
bidirectional at the structural layer; collapsing `EntryActionability`
into a directionless state would lose real information the upstream
Decision already carries.

Entry/stop/target representation is deferred as **shape, not formula**:
nested immutable value objects (e.g. a proposed entry zone, an
invalidation/stop reference, a reward/target zone — exact names and all
numeric methodology left to ID-7B), mirroring `TradePlan`'s own existing
pattern of being a nested immutable value object inside `Decision`, rather
than an opaque JSON blob. No entry buffer %, stop multiplier, chase limit,
minimum RR, VWAP distance, spread limit, volume threshold, resistance
distance, time-stop, or slippage % is invented here. T1/T2 (~+1%/~+1.5%)
remain product/research goal bands, not engine formulas.

No canonical support/resistance engine exists outside DarvaX (confirmed:
no `support`/`resistance`/`fibonacci` implementation anywhere in
`src/athena/` except DarvaX's own isolated `primitives/levels.py`, which
`api/darvax_mount.py` explicitly refuses to interpret). If a future ID-7B
methodology needs structural levels, `OpeningRangeEvidence` (ID-3, already
real and available) is the nearest existing candidate; a generalized
support/resistance engine is recorded as an open methodology/data
dependency for ID-7B/ID-8, not built here. DarvaX remains untouched and
unreferenced.

**Persistence direction (design only, no schema created):** append-only,
mirroring `entry_qualifications`' own shape — the copied EQ key plus
`entry_actionability_as_of`/`entry_actionability_methodology_version` as
primary key, `state`, `reason_codes`, `evidence_refs`,
`evidence_as_of`/`evaluated_at`/`persisted_at`, `config_snapshot_id`,
`explanation`, and (once ID-7B exists) the nested entry/stop/target value
objects. No destructive updates, no supersession write. "Latest" (by
`entry_actionability_as_of`) is a **query convention**
(`ORDER BY ... DESC LIMIT`), exactly as it is today for both `Decision`
and `EntryQualification` — never a persisted supersession marker. "Latest
*currently usable*" is **not** a `state`-filtered query alone (an old
`ACTIONABLE` row is not usable merely because no `EXPIRED` row exists —
see Decision, dimension (B)) — it additionally requires the derived
`is_currently_usable(...)` read-time predicate. A future repository would
need, at minimum: exact-key lookup, latest-for-instrument/session (a
methodology-state view), latest-bound-to-the-current-Decision/EQ (an
identity-currentness view), latest-currently-usable (applying the full
`is_currently_usable` predicate), and a full oldest-first
history/trajectory view for audit — mirroring and extending EQ's own
method family.

**Workflow direction (design only, no stage created):** the same
canonical per-instrument `WorkflowStage` DAG `OwnerValidationPipeline`
already drives (`src/athena/ops/owner_validation.py`,
`src/athena/runtime/workflow.py`). A new stage, declared with no
dependents (nothing else naming it in `depends_on`), attaches without
perturbing any existing stage's order — exactly the non-perturbation
property already asserted in code comments for the `session` and
`entry_qualification` stages. No new worker, no new daemon thread, no
ADR-014-style satellite process — that pattern exists for EMR's
structurally different, independently-scheduled candidate-scanning
concern and is not a template for a per-instrument, per-cycle domain
stage.

**Provider boundary:** the future `entry_actionability` stage reads only
already-ingested-this-cycle `WorkflowContext` outputs (candles, quotes,
`IntradaySignalSet`, the bound `Decision`/`EntryQualification`) — never a
direct Kite call. Provider acquisition and domain evaluation remain
separate concerns, exactly as today.

**Freshness/evaluation-mode conclusion:** Option 1 is frozen as the
initial architecture *because* it requires zero new infrastructure, zero
new provider traffic, and yields the strongest possible determinism (the
`EntryActionability` row is produced inside the identical
`WorkflowExecution` as the `Decision`/`EntryQualification` it binds to —
no race, no separate identity-resolution step). It necessarily inherits
`EntryQualification`'s own existing freshness ceiling (up to the
canonical cycle's ≈9-10 minute duration) — the same ceiling ID-6 was
already owner-approved under. The identity model above (a distinct
`entry_actionability_as_of` dimension, independent of `evaluated_at`) is
deliberately chosen so that a **future** stricter-freshness evaluation
mode (Option 2, asynchronous-after-ingestion) could later produce
additional `EntryActionability` rows against the *same* bound EQ at a
*later* `entry_actionability_as_of`, without any identity/schema
redesign. Whether that future mode is ever needed is explicitly **not
decided here** — see Alternatives considered, Option 2, and Consequences.

## Alternatives considered

**Artifact naming — `TradePlan`/`IntradayTradePlan`.** Rejected: both
collide semantically with the existing, frozen, Decision-embedded
`TradePlan`, and the discovery report already established that entity
cannot be reused or overloaded (Option B). `EntryActionability` was
chosen over the other brainstormed labels (`Actionability`,
`IntradayAction`, `ExecutionOpportunity`, `EntryWindow`) because it names
the artifact's purpose precisely (an entry-actionability assessment, not
a generic "action" or an execution/order-shaped noun), and because it
extends `EntryQualification`'s own established naming family (`Entry*`),
signaling the WHETHER→WHEN relationship directly.

**Identity — Option B (bind through a persisted EQ identifier introduced
later).** Rejected. `EntryQualification` has no surrogate id today
(confirmed from schema and domain model); introducing one now would
require reopening the frozen, owner-approved-and-closed ID-6C persistence
contract for a module this ADR has no mandate to modify. Option C (some
other immutable equivalent) was considered and found unnecessary — Option
A (copy the full canonical key) is directly available, requires no
upstream change, and is sufficient.

**Evaluation mode — Option 2, asynchronous after ingestion.** Considered
in depth. Because `EntryActionability` must bind to an *exact* EQ
identity (Decision constraint 4/5), an async evaluator cannot
meaningfully start before EQ itself is computed and persisted — EQ is
itself already the last stage in the synchronous per-instrument DAG for
that cycle. Decoupling evaluation from the DAG would not, on its own,
buy earlier evidence; it would only add a new trigger/event mechanism,
new race-condition exposure (which Decision/EQ is "current" by the time
the async evaluator runs, given decision churn — §Consequences), and a
new idempotency requirement, for no measurable freshness gain absent a
change to *how EQ itself* becomes available sooner. Not chosen now; the
identity model does not foreclose it later if ID-7B proves it necessary.

**Evaluation mode — Option 3, event-driven market-evidence path.**
Rejected for this milestone: no event bus or pub/sub infrastructure
exists anywhere in ATHENA today (`WorkflowStage`/`WorkflowEngine` is a
synchronous, in-process DAG walk, not an event system). Building one
would be new infrastructure this ADR is not authorized to create (and
would itself constitute exactly the kind of "solve latency by building
new infra" work explicitly out of scope for ID-7A0).

**Evaluation mode — Option 4, on-demand/API-time.** Rejected as primary
architecture: breaks reproducibility (two requests at different times
against the "same" Decision would non-deterministically produce different
results), invites future provider-call temptation inside a request
handler (violating the provider/domain separation above), and is
structurally weaker for audit/replay than a persisted artifact — the same
reasoning that led ID-6 to persist `EntryQualification` rather than
compute it on demand.

**Evaluation mode — Option 5, hybrid (persisted async + on-demand
freshness check).** Considered and deferred, not rejected outright. Adds
real complexity (two evaluation paths, two consistency stories) with no
demonstrated present need — Option 1 already satisfies determinism,
replay, identity, and zero-new-infrastructure cleanly, and shares the
exact freshness ceiling EQ itself already operates under. Revisit only if
ID-7B's own methodology proves canonical-cycle freshness insufficient.

**WATCH/TRADE scope — `WATCH`+`TRADE` (mirroring EQ's own scope exactly).**
Rejected (ID-7A0.1 correction). The original ADR reasoned this was a
*forced* consequence of EQ-identity binding — that framing was too
strong: identity binding only establishes that `EntryActionability`
cannot exist without a bound EQ row, not that its evaluation scope must
match EQ's. Testing the actual semantics (Decision, WATCH/TRADE scope
above) found that surfacing WHEN/entry/risk evidence for a structurally
un-authorized (`WATCH`) opportunity would misrepresent ATHENA's own
advisory boundary. **`TRADE`-only evaluation scope selected instead** —
see Decision.

**WATCH/TRADE scope — silently exclude `WATCH` (no row at all).**
Considered as the mechanism for enforcing TRADE-only scope. Rejected in
favor of still creating a `NOT_ACTIONABLE` row with an explicit
"bound Decision is not TRADE-type" reason code — silent exclusion would
recreate exactly the explainability ambiguity ("did the stage even run?")
the upstream-not-ready policy (Option C) was already chosen to avoid one
paragraph earlier; there is no principled reason to treat "wrong
Decision type" differently from "EQ not ready" when both are equally
explainable, equally point-in-time, blocking conditions.

**Persisted `EXPIRED` methodology state.** Rejected (ID-7A0.1 correction,
Option A). See Decision — no code path under the selected Option 1
architecture ever writes it, and retaining it would conflate a read-time
currentness concern with a point-in-time methodology fact. Considered
retaining it and requiring proof of "what deterministic evaluation event
writes it" per the authorization's own test; no such event exists under
Option 1, so the option fails that test and was dropped rather than
force-fit.

## Consequences

**Easier:** ID-7B (entry/risk methodology) can be designed and reviewed
against a frozen identity/lifecycle/persistence contract, exactly as
ID-6B was against ADR-013 — without re-litigating WHAT the artifact is
bound to, when it's created, or how staleness is represented. The
methodology-state (A) / freshness-currentness (B) / finality-provenance
(C) separation means ID-7B only has to freeze *thresholds* (the exact
freshness policy inside `is_currently_usable`, the exact entry/stop/
target formulas) against an already-coherent lifecycle — it never has to
re-derive the lifecycle itself. A future UI consumer has an explicit,
queryable "is this actionability still bound to the current Decision/EQ,
and still fresh enough to use" check (`is_currently_usable`, comparing
the stored `decision_id` against `list_latest_decisions_by_instrument()`'s
current row plus an evidence-age test) rather than an implicit,
easy-to-get-wrong assumption, and can display a historically-`ACTIONABLE`
row without it silently masquerading as currently actionable.

**Harder / accepted debt:** `EntryActionability`, under Option 1, inherits
the full ≈9-10 minute canonical cycle latency as its evidence-freshness
ceiling — identical to `EntryQualification`'s own already-accepted
ceiling, but now the *dominant* open question for a layer whose entire
purpose is WHEN. This ADR does not resolve whether that ceiling is
acceptable for ID-7's eventual target entry timescale — ID-7P0's own
Recommendation A is non-binding, and this ADR classifies that question
**A_CANNOT_BE_DECIDED_UNTIL_ID7B** (see the required research report,
§28). If ID-7B's methodology later requires materially fresher evidence,
Option 2/3/5 becomes a **separate, explicitly authorized latency/
architecture revision** — not a silent evolution of this ADR.

**Decision churn must be respected, not silently absorbed.** Production
issues a fresh canonical `Decision` (and a fresh `EntryQualification`)
every cycle. `Decision D1 + EQ1 → EntryActionability A1` and
`Decision D2 + EQ2 → EntryActionability A2` are and must remain distinct,
immutable rows — A1 is never mutated into A2. "Latest actionability" is a
read-time query convention only, exactly mirroring the successful ID-6
persistence philosophy this ADR deliberately reuses.

**Must be revisited:** ID-7A (domain model/schema), ID-7B (methodology),
ID-7C (engine), ID-7E (workflow wiring), and ID-7F (replay/shadow
validation) each require their own separate owner authorization,
mirroring ADR-013's own ID-6A0→ID-6E gated sequence. None is authorized
by this ADR. If ID-7B's methodology later needs structural
support/resistance levels beyond `OpeningRangeEvidence`, that is a
methodology/data dependency to record at that time, not to build now.

**Correction (2026-09-05, ID-7D discovery, Owner-accepted):** this list
originally also named a separate "ID-7D (persistence)" milestone. The
real ID-7A authorization later bundled domain model AND persistence into
one milestone (schema v18, the `entry_actionabilities` table, the full
append-only repository contract) — ID-7D's entire originally-planned
scope was absorbed into ID-7A as actually executed, and no separate
ID-7D implementation milestone exists. See
`docs/research/ID-7D-NEXT-LAYER-DISCOVERY-CONTRACT-RECONCILIATION.md`
for the full reconciliation. This note corrects the stale reference in
place rather than rewriting the ADR's original history.
ID-9 (sizing), ID-10 (live plan supervision), and ID-11 (execution
quality) remain explicitly out of scope — `EntryActionability` may expose
risk-distance evidence those later layers consume, but performs no
capital allocation, no ongoing position supervision, and integrates no
depth/liquidity feed itself.

**Replay limitation carried forward, not resolved:** exactly as ADR-013
already documents for `EntryQualification`, ATHENA supports genuine
market-time point-in-time replay (`repository.py`'s `as_of`-bounded reads)
but not full bitemporal/knowledge-time replay (no tracking of when a row
was actually known to the system). `EntryActionability`'s replay
semantics inherit this same limitation; a future replay/shadow milestone
(ID-7F) must state it explicitly, exactly as ID-6E's own replay harness
already does for `EntryQualification`.
