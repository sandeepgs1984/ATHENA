# ADR-003 — PipelineContext over Direct Module Calls

| | |
|---|---|
| Status | Accepted |
| Date | 2026-07-20 |
| Deciders | sandeep (owner, ATHENA-002R F-1), engineering review |

> **Revised by Amendment 1** (ID-P0, 2026-08-29, see the end of this
> document): the concrete mechanism described below —
> `domain.context.PipelineContext` / `ContextDelta` / `IntelligenceModule` —
> was never adopted by the live pipeline and has zero production callers.
> The canonical runtime implementing this ADR's *intent* (typed
> producer/consumer declarations, deterministic DAG execution, no hidden
> coupling) is `runtime.workflow.WorkflowContext` / `WorkflowStage` /
> `WorkflowDefinition` / `WorkflowEngine`. The Decision/Alternatives/
> Consequences below describe the ORIGINAL, now-superseded design; read
> Amendment 1 for what is actually authoritative.

## Context

Modules must collaborate (regime→risk, portfolio→capital, journal→confidence; ATHENA-001R R-12) without coupling. Direct calls create an import web; a message bus is overkill for one process.

## Decision

A single immutable `PipelineContext` — run context, calendar, market, portfolio, config snapshot, provider handle, cycle metadata, and all outputs so far — passes through every module. Modules declare `consumes`/`produces` keys and return `ContextDelta`s; the orchestrator applies them in DAG order (ATHENA-002 §7.1).

## Alternatives considered

Direct module calls — rejected: hidden coupling, untestable in isolation. Event bus (pub/sub) in v1 — rejected: premature; the declared-keys contract already enables the event-driven upgrade (§8.4) as a runtime-only change.

## Consequences

Modules are pure functions of context → delta: trivially testable, deterministic, replayable. Cost: the context type must be maintained as the true shared contract, and large intermediate outputs live in memory for the cycle (acceptable at watchlist scale).

---

## Amendment 1 — Adopt `WorkflowContext`/`WorkflowStage` as the canonical runtime; retire `PipelineContext`/`ContextDelta`/`IntelligenceModule` as dormant

| | |
|---|---|
| Status | **Accepted** (2026-08-29) — supersedes the concrete mechanism in the Decision above; the ADR's intent (typed contracts, no hidden coupling, deterministic DAG order) stands unchanged |
| Date | 2026-08-29 |
| Deciders | sandeep (owner), per ID-P0 |
| Evidence | `docs/research/ID-0-RUNTIME-AUDIT-ARCHITECTURE-REPORT.md` §4, §13 |

### Context

ID-0's runtime audit (2026-08-29) traced every one of ATHENA's six
scheduled/triggered decision flows end to end and found that
`domain.context.PipelineContext`, `ContextDelta`, and the
`IntelligenceModule` Protocol (`domain/interfaces.py`) — the concrete
mechanism this ADR originally specified — have **zero non-test callers**
anywhere in the codebase. No analytical engine implements
`IntelligenceModule`; no production code constructs a `PipelineContext` or
applies a `ContextDelta`. The only code that exercises these types is an
isolated unit test of the dataclasses themselves
(`tests/unit/test_domain.py`).

The pipeline that has actually run every PREMARKET/REFRESH/FAST/CLOSING/
Revalidate/full-validation cycle since M4.1 is a different, independently
implemented mechanism: `runtime.workflow.WorkflowContext` /
`WorkflowStage` / `WorkflowDefinition` / `WorkflowEngine`
(`src/athena/runtime/workflow.py`), wired together per-instrument inside
`OwnerValidationPipeline._scan_eligible`
(`src/athena/ops/owner_validation.py`). It already satisfies this ADR's
actual intent — modules as pure functions over declared inputs/outputs, no
hidden coupling, deterministic execution order, replayable — through its
own, different types:

- `WorkflowStage(name, run, depends_on, produces)` — the equivalent of a
  module declaring `consumes`/`produces`, expressed as a dependency tuple
  and a produced-keys tuple instead of frozensets on a Protocol.
- `WorkflowContext` — a per-run accumulator stages read from and never
  mutate directly (`get`/`has`), functionally equivalent to
  `PipelineContext.get`/`.has`, but a plain dict-backed accumulator rather
  than a frozen dataclass rebuilt on every delta.
- `WorkflowDefinition._topological_order` — a deterministic Kahn
  topological sort (ties broken by declaration order) that IS this ADR's
  "orchestrator applies them in DAG order," just not literally
  `ContextDelta`-shaped.
- `WorkflowEngine.execute` — failure isolation (a failed/blocked stage's
  dependents are marked SKIPPED, independent branches still run) and
  per-stage timing via an injected clock, for bit-identical replay.

Two mechanisms claiming to be "the pipeline contract" — one dormant, one
live and undocumented as canonical — is a real risk for the Intraday
Intelligence program, which is about to add new stages to this pipeline.
Building on the wrong (dormant) one would be silent, discovered only when
the new stage never actually runs.

### Decision

**`runtime.workflow.WorkflowContext` / `WorkflowStage` /
`WorkflowDefinition` / `WorkflowEngine` is ATHENA's canonical production
pipeline runtime**, effective immediately. This is a documentation
correction, not a migration: the live pipeline already uses this
mechanism and is not being changed.

`domain.context.PipelineContext`, `ContextDelta`, and the
`IntelligenceModule` Protocol are **dormant/legacy scaffolding** and
**MUST NOT** be used for any new production stage, including every future
Intraday Intelligence (ID-1 → ID-13) stage. They are not deleted in this
amendment — deletion requires a separate cleanup milestone with its own
dependency verification (none of these types has been proven completely
safe and trivial to remove; `domain/__init__.py` still re-exports them,
and `domain/interfaces.py`'s `IntelligenceModule` still references them).
Their module-level docstrings are updated to state this plainly (see
`domain/context.py`, `domain/interfaces.py`).

**Canonical rule for every future pipeline stage** (this is now the
authoritative pattern for ID-1 and beyond, not merely a description of
what already exists):

1. A stage is a `WorkflowStage` instance: `name`, a `run(ctx) -> Mapping`
   callable, `depends_on` (the stage names it genuinely reads output
   from), and `produces` (the context keys it writes).
2. A stage's inputs are exactly its declared `depends_on` dependencies —
   never an incidental read of a context key a stage happens to have
   access to without declaring the dependency that produces it.
3. A stage's outputs are returned from `run()` and placed into
   `WorkflowContext` by `WorkflowEngine._merge` — a stage never mutates
   the context directly, and re-producing an existing key is a hard
   error (`WorkflowError`), not silently overwritten.
4. `WorkflowDefinition`/`WorkflowEngine` determine execution order via
   deterministic topological sort — **stage authors must not rely on
   declaration order** for anything semantic. (The live graph is proof
   this matters: `risk` executes before `confidence` today despite being
   declared after it, because `risk`'s dependencies are satisfied one
   round earlier — see the ID-0 report §2.)
5. Every real dependency must be declared explicitly in `depends_on`. A
   stage that reads `ctx.get("regime")` without declaring
   `depends_on=(..., "regime")` is a latent bug: `WorkflowContext.get`
   raises `KeyError` if the producer hasn't run yet, and nothing prevents
   an accidental read succeeding today only by execution-order luck if
   the dependency is omitted.
6. Deterministic/replayable execution is preserved exactly as it is
   today: `WorkflowEngine` takes an injected clock, `as_of` is passed
   explicitly into every stage via `WorkflowContext.as_of`, and no stage
   may read a wall clock, call `datetime.now()`, or otherwise introduce
   hidden state.

No existing stage's execution behavior changes as a result of this
amendment — this is a documentation and guard-rail change only (see the
architecture test added alongside this amendment, §13 of the ID-0
report).

### Alternatives considered

**Migrate the live pipeline onto `domain.context.PipelineContext`/
`ContextDelta`/`IntelligenceModule`** — rejected. The Workflow runtime is
already deterministic, tested, and production-live across every
scheduled trigger; migrating the entire pipeline immediately before the
Intraday Intelligence expansion would introduce real architectural risk
(re-wiring six analytical engines' call sites, re-verifying replay
determinism, re-testing every trigger path) for no functional gain — both
mechanisms already satisfy this ADR's actual intent.

**Leave both undocumented and let each future contributor discover the
live one by tracing code** — rejected. This is exactly the failure mode
ID-0 was commissioned to catch before Intraday Intelligence starts adding
stages.

### Consequences

- `WorkflowContext`/`WorkflowStage`/`WorkflowDefinition`/`WorkflowEngine`
  are now documented as the one true pipeline mechanism — no ambiguity for
  ID-1 onward.
- `domain.context.PipelineContext`/`ContextDelta`/`IntelligenceModule`
  remain in the codebase, clearly marked dormant, until a dedicated
  cleanup milestone verifies deletion is safe.
- `docs/ATHENA-TECHNICAL-ARCHITECTURE.md` and
  `docs/ATHENA-WORKFLOW-METHODOLOGY.md` are corrected wherever they
  presented `PipelineContext`/`ContextDelta` as the live mechanism (see
  ID-P0's Milestone Review Summary for the exact passages changed).
- A new architecture test (`tests/architecture/test_pipeline_mechanism_boundary.py`)
  fails the suite if a second pipeline mechanism starts being used in
  production code, so this ambiguity cannot silently reappear during
  Intraday Intelligence development.
