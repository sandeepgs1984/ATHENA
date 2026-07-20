# ATHENA — Project Rules

## Git actions rule (mandatory)

The AI must NEVER run git actions (add, commit, push, pull, checkout, branch, merge, etc.) on its own. The AI edits files only. For every change set, the AI provides ONLY the consolidated commit message (per the rule below) — no cd/add/commit command boilerplate — for sandeep to use himself. Git actions may only be executed by the AI if sandeep explicitly asks for it in that specific instance.

## Git commit rule (mandatory)

Every change to this project must be committed with a proper, consolidated commit message:

- One commit per logical change set — never scatter one change across commits, never pile unrelated changes into one.
- Format: `<type>(<scope>): <summary>` on the first line (≤72 chars, imperative mood), blank line, then a body as bullet points (`-`), one point per distinct change, each stating WHAT and WHY — never one big paragraph.
- Types: `docs`, `feat`, `fix`, `config`, `test`, `refactor`, `chore`.
- Scopes: `constitution`, `review`, or module names once code exists (`data`, `evidence`, `scoring`, `risk`, `decision`, `report`).
- Reference the governing doc/amendment where relevant (e.g., "per ATHENA-001 amendment 7").

Example:

```
docs(review): resolve journal phase inconsistency in ATHENA-001

Aligned U-2 with the phase plan: journal is a Phase 3 deliverable.
Per ATHENA-001 §2 D-3.
```

## Implementation rules (mandatory — architecture is FROZEN)

- Build correctly, not quickly: optimize for correctness, simplicity, determinism, explainability, maintainability, testability, replayability.
- Before writing any code: review the relevant ATHENA-002 section; confirm alignment with the Constitution, Blueprint, ADRs, phase scope, and Definition of Done. If anything conflicts, ASK before implementing. Never silently change architecture; genuine architectural limitations → stop, document, propose an ADR, wait for approval.
- Engineering principles: clarity over cleverness; simplicity over abstraction; configuration over hardcoding; pure functions; one responsibility per module/class/function; deterministic execution; no hidden state; no magic numbers; explicit contracts; every calculation explainable; every failure fails loudly; composition over inheritance; minimal dependencies; business logic independent of providers.
- Phase discipline: exactly one phase at a time; next phase only after all documented acceptance criteria pass. No speculative features, no placeholders unless explicitly requested, no anticipating future phases.
- After each milestone: STOP. Produce the 7-part summary (completed work, architectural compliance, files created, tests added, remaining work, risks discovered, implementation-only improvement suggestions) and wait for approval.

## Project context

Single-user decision-intelligence platform for NSE/BSE swing trading. Constitution: ATHENA-000. Engineering review and 12 accepted amendments: ATHENA-001. Never add order-placement code. Secrets in `.env` only. See README for stack decisions.
