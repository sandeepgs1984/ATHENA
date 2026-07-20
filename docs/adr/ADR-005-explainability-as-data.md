# ADR-005 — Explainability as Data, Not an Engine

| | |
|---|---|
| Status | Accepted |
| Date | 2026-07-20 |
| Deciders | sandeep (owner), engineering review (ATHENA-001 A-2) |

## Context

ATHENA-000 originally placed an "Explainability Engine" near the end of the pipeline. A terminal engine cannot reconstruct upstream reasoning — it can only decorate, which is how black boxes are born.

## Decision

Explanation is a field, not a stage. Every Evidence, Score, RiskEvaluation, and Decision carries its rationale (rule fired, values observed, threshold used) at creation time; the DecisionTrace (F-15) assembles the full reasoning path; the report module renders and never computes. Recommendations failing the explainability quality gate (§8.5) are rejected automatically (R-8).

## Alternatives considered

Terminal explainability engine — rejected: reconstruction is lossy and eventually dishonest. LLM-generated post-hoc explanations — rejected as the source of truth: AI may rephrase recorded rationale (§18) but never originate it.

## Consequences

Explainability is enforceable by schema (non-null explanation fields) and testable (gate + golden expectations). Cost: every module author writes the "why" at the point of computation — deliberate friction the constitution's principle 1 demands.
