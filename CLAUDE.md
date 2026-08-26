# ATHENA — Project Rules

@ATHENA_BRIEFING.md

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

## Expensive external-data runs (mandatory)

Adopted 2026-08-24, after a real ~49-hour EM-1r3 production capture (518
instruments, live Kite API) ran to completion against a defective provider
request boundary and produced ~0% usable admission — a systemic defect a
few seconds of real-provider checking would have caught before the sweep
even started.

- Before launching any expensive real-provider operation (long-running,
  large API-call volume, or otherwise costly to redo), run a small,
  **real-provider canary** first: a handful of representative real calls
  covering the shape of what the full run will do (old data, recent data,
  and any known edge cases the domain has).
- Define an **explicit, numeric admission/quality threshold** for the
  canary up front — not a vibe check. A canary that "ran without crashing"
  proves nothing; it must prove the data coming back is actually usable at
  a stated rate.
- **Automatically fail fast** if the canary misses the threshold: refuse
  to proceed to the full run, with a clear message naming what failed and
  why. This must be the default behavior of the launcher itself, not a
  step a human has to remember to run separately.
- A canary must correctly distinguish a **systemic defect** (the failure
  mode this rule exists to catch) from a **known, already-diagnosed,
  bounded limitation** of the data source — never let it fail on the
  latter, or the gate will be disabled out of frustration the first time
  it fires on a case everyone already understands.
- See `src/athena/data/em1r3_production_canary.py` for the reference
  implementation and `tests/data_layer/test_em1r3_production_canary.py`
  for what "prove it catches the real incident shape" looks like in
  practice.

## Milestone workflow (mandatory — official development standard)

- Every phase divides into small, independently reviewable milestones (roadmap: `docs/MILESTONES.md`). Cycle per milestone: Design → Implement → Test → Self-Validate → Milestone Review Summary → owner/principal-engineer review → approval → next milestone. NEVER auto-continue to the next milestone; always stop and wait for approval.
- Each milestone must be small enough for a complete code review in one sitting; if it grows too large, split it BEFORE implementing. Implement only the approved milestone scope — no future-phase code, no placeholders, no TODO implementations, no speculative abstractions, no unnecessary refactoring.
- Preserve at all times: architectural boundaries, determinism, replayability, explainability, immutable domain objects, contract compatibility, provider independence. If implementation requires an architecture change: STOP, write an ADR proposal, wait — never implement the change.
- Before marking any milestone complete, verify ALL of: (1) full test suite passes, (2) architectural compliance, (3) frozen contracts unchanged, (4) replayability preserved, (5) deterministic behaviour, (6) no ADR required, (7) no architecture drift, (8) quality gates pass, (9) configuration compatibility, (10) documentation accuracy.
- Every milestone ends with a Milestone Review Summary: name, objective, scope completed, files created, files modified, public APIs added, tests added, test results, coverage summary, architecture compliance, ADR compliance, risks discovered, technical debt introduced, suggested improvements, remaining work, commit message, ready-for-review.
- Update `IMPLEMENTATION_SUMMARY.md` (repo root, permanent implementation log) after EVERY completed milestone and phase. Phase entries include: summary, architecture compliance, files created, tests added, remaining work, risks, suggested improvements, lessons learned, implementation metrics, phase outcome, commit hash, branch, review status.
- When a track/phase closes, or the module map materially changes, update `ATHENA_BRIEFING.md` §6 (repo map) in the same change set — it is the fast-orientation doc every AI agent reads first and must never drift from reality.

## Project context

Single-user decision-intelligence platform for NSE/BSE swing trading. Constitution: ATHENA-000. Engineering review and 12 accepted amendments: ATHENA-001. Never add order-placement code. Secrets in `.env` only. See README for stack decisions. See `ATHENA_BRIEFING.md` for the full AI-agent orientation map (what ATHENA is, governing docs, how to find current status, repo map) — read it first, every session.

## Imported Claude Cowork project instructions

<!-- rtk-instructions v2 -->
# RTK (Rust Token Killer) - Token-Optimized Commands

## Golden Rule

**Always prefix commands with `rtk`**. If RTK has a dedicated filter, it uses it. If not, it passes through unchanged. This means RTK is always safe to use.

**Important**: Even in command chains with `&&`, use `rtk`:
```bash
# ❌ Wrong
git add . && git commit -m "msg" && git push

# ✅ Correct
rtk git add . && rtk git commit -m "msg" && rtk git push
```

## RTK Commands by Workflow

### Build & Compile (80-90% savings)
```bash
rtk cargo build         # Cargo build output
rtk cargo check         # Cargo check output
rtk cargo clippy        # Clippy warnings grouped by file (80%)
rtk tsc                 # TypeScript errors grouped by file/code (83%)
rtk lint                # ESLint/Biome violations grouped (84%)
rtk prettier --check    # Files needing format only (70%)
rtk next build          # Next.js build with route metrics (87%)
```

### Test (60-99% savings)
```bash
rtk cargo test          # Cargo test failures only (90%)
rtk go test             # Go test failures only (90%)
rtk jest                # Jest failures only (99.5%)
rtk vitest              # Vitest failures only (99.5%)
rtk playwright test     # Playwright failures only (94%)
rtk pytest              # Python test failures only (90%)
rtk rake test           # Ruby test failures only (90%)
rtk rspec               # RSpec test failures only (60%)
rtk test <cmd>          # Generic test wrapper - failures only
```

### Git (59-80% savings)
```bash
rtk git status          # Compact status
rtk git log             # Compact log (works with all git flags)
rtk git diff            # Compact diff (80%)
rtk git show            # Compact show (80%)
rtk git add             # Ultra-compact confirmations (59%)
rtk git commit          # Ultra-compact confirmations (59%)
rtk git push            # Ultra-compact confirmations
rtk git pull            # Ultra-compact confirmations
rtk git branch          # Compact branch list
rtk git fetch           # Compact fetch
rtk git stash           # Compact stash
rtk git worktree        # Compact worktree
```

Note: Git passthrough works for ALL subcommands, even those not explicitly listed.

### GitHub (26-87% savings)
```bash
rtk gh pr view <num>    # Compact PR view (87%)
rtk gh pr checks        # Compact PR checks (79%)
rtk gh run list         # Compact workflow runs (82%)
rtk gh issue list       # Compact issue list (80%)
rtk gh api              # Compact API responses (26%)
```

### JavaScript/TypeScript Tooling (70-90% savings)
```bash
rtk pnpm list           # Compact dependency tree (70%)
rtk pnpm outdated       # Compact outdated packages (80%)
rtk pnpm install        # Compact install output (90%)
rtk npm run <script>    # Compact npm script output
rtk npx <cmd>           # Compact npx command output
rtk prisma              # Prisma without ASCII art (88%)
rtk uv run <cmd>        # Compact uv project command output
```

### Files & Search (60-75% savings)
```bash
rtk ls <path>           # Tree format, compact (65%)
rtk read <file>         # Code reading with filtering (60%)
rtk grep <pattern>      # Search grouped by file (75%). Format flags (-c, -l, -L, -o, -Z) run raw.
rtk find <pattern>      # Find grouped by directory (70%)
```

### Analysis & Debug (70-90% savings)
```bash
rtk err <cmd>           # Filter errors only from any command
rtk log <file>          # Deduplicated logs with counts
rtk json <file>         # JSON structure without values
rtk deps                # Dependency overview
rtk env                 # Environment variables compact
rtk summary <cmd>       # Smart summary of command output
rtk diff                # Ultra-compact diffs
```

### Infrastructure (85% savings)
```bash
rtk docker ps           # Compact container list
rtk docker images       # Compact image list
rtk docker logs <c>     # Deduplicated logs
rtk kubectl get         # Compact resource list
rtk kubectl logs        # Deduplicated pod logs
```

### Network (65-70% savings)
```bash
rtk curl <url>          # Compact HTTP responses (70%)
rtk wget <url>          # Compact download output (65%)
```

### Meta Commands
```bash
rtk gain                # View token savings statistics
rtk gain --history      # View command history with savings
rtk discover            # Analyze Claude Code sessions for missed RTK usage
rtk proxy <cmd>         # Run command without filtering (for debugging)
rtk init                # Add RTK instructions to CLAUDE.md
rtk init --global       # Add RTK to ~/.claude/CLAUDE.md
```

## Token Savings Overview

| Category | Commands | Typical Savings |
|----------|----------|-----------------|
| Tests | vitest, playwright, cargo test | 90-99% |
| Build | next, tsc, lint, prettier | 70-87% |
| Git | status, log, diff, add, commit | 59-80% |
| GitHub | gh pr, gh run, gh issue | 26-87% |
| Package Managers | pnpm, npm, npx | 70-90% |
| Files | ls, read, grep, find | 60-75% |
| Infrastructure | docker, kubectl | 85% |
| Network | curl, wget | 65-70% |

Overall average: **60-90% token reduction** on common development operations.
<!-- /rtk-instructions -->