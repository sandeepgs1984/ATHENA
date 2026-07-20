# ADR-003 — PipelineContext over Direct Module Calls

| | |
|---|---|
| Status | Accepted |
| Date | 2026-07-20 |
| Deciders | sandeep (owner, ATHENA-002R F-1), engineering review |

## Context

Modules must collaborate (regime→risk, portfolio→capital, journal→confidence; ATHENA-001R R-12) without coupling. Direct calls create an import web; a message bus is overkill for one process.

## Decision

A single immutable `PipelineContext` — run context, calendar, market, portfolio, config snapshot, provider handle, cycle metadata, and all outputs so far — passes through every module. Modules declare `consumes`/`produces` keys and return `ContextDelta`s; the orchestrator applies them in DAG order (ATHENA-002 §7.1).

## Alternatives considered

Direct module calls — rejected: hidden coupling, untestable in isolation. Event bus (pub/sub) in v1 — rejected: premature; the declared-keys contract already enables the event-driven upgrade (§8.4) as a runtime-only change.

## Consequences

Modules are pure functions of context → delta: trivially testable, deterministic, replayable. Cost: the context type must be maintained as the true shared contract, and large intermediate outputs live in memory for the cycle (acceptable at watchlist scale).
