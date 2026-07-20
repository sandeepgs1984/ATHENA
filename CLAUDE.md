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
## Milestone workflow (mandatory — official development standard)

- Every phase divides into small, independently reviewable milestones (roadmap: `docs/MILESTONES.md`). Cycle per milestone: Design → Implement → Test → Self-Validate → Milestone Review Summary → owner/principal-engineer review → approval → next milestone. NEVER auto-continue to the next milestone; always stop and wait for approval.
- Each milestone must be small enough for a complete code review in one sitting; if it grows too large, split it BEFORE implementing. Implement only the approved milestone scope — no future-phase code, no placeholders, no TODO implementations, no speculative abstractions, no unnecessary refactoring.
- Preserve at all times: architectural boundaries, determinism, replayability, explainability, immutable domain objects, contract compatibility, provider independence. If implementation requires an architecture change: STOP, write an ADR proposal, wait — never implement the change.
- Before marking any milestone complete, verify ALL of: (1) full test suite passes, (2) architectural compliance, (3) frozen contracts unchanged, (4) replayability preserved, (5) deterministic behaviour, (6) no ADR required, (7) no architecture drift, (8) quality gates pass, (9) configuration compatibility, (10) documentation accuracy.
- Every milestone ends with a Milestone Review Summary: name, objective, scope completed, files created, files modified, public APIs added, tests added, test results, coverage summary, architecture compliance, ADR compliance, risks discovered, technical debt introduced, suggested improvements, remaining work, commit message, ready-for-review.
- Update `IMPLEMENTATION_SUMMARY.md` (repo root, permanent implementation log) after EVERY completed milestone and phase. Phase entries include: summary, architecture compliance, files created, tests added, remaining work, risks, suggested improvements, lessons learned, implementation metrics, phase outcome, commit hash, branch, review status.

## Project context

Single-user decision-intelligence platform for NSE/BSE swing trading. Constitution: ATHENA-000. Engineering review and 12 accepted amendments: ATHENA-001. Never add order-placement code. Secrets in `.env` only. See README for stack decisions.
