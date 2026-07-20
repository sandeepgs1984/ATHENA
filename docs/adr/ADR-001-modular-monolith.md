# ADR-001 — Modular Monolith over Independent Engines

| | |
|---|---|
| Status | Accepted |
| Date | 2026-07-20 |
| Deciders | sandeep (owner), engineering review board (ATHENA-001) |

## Context

ATHENA-000 described 13 "independently replaceable" intelligence engines. For a single-user local Python application, independent engines mean process boundaries, duplicated harnesses, and a dependency graph maintained by one person (ATHENA-001 A-1, D-1).

## Decision

Build one process, one repo: a modular monolith of 17 modules (ATHENA-002 §2) behind `typing.Protocol` interfaces. Replaceability comes from interfaces and the frozen domain model, not process boundaries.

## Alternatives considered

Independent engines/services — rejected: operational complexity with zero benefit at single-user scale. Single unstructured codebase — rejected: violates constitution principle 5 (modularity) and blocks module graduation later.

## Consequences

Faster working software; module graduation (e.g., learning as separate process) remains possible via the Protocol seam at the cost of a small refactor. Discipline required: no module imports another intelligence module — enforced by the PipelineContext contract (ADR-003).
