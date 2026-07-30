# ATHENA Advisor Workbench Polish Roadmap

**Status:** approved for AW-1 start on 2026-07-30  
**Scope:** Decisions & Trace entry readiness plus Market Intelligence daily-use polish  
**Owner goal:** make ATHENA easier to use during a live trading day without
adding order placement, fabricated signals, or unreviewed analytical changes.

## 1. Governing Boundaries

- ATHENA remains advisory-only. It never places orders, prepares broker
  baskets, or calls broker write APIs.
- Entry-readiness UX may compare an existing live quote with the persisted
  TradePlan entry zone, but it must not change ATHENA's decision, score, risk,
  confidence, entry, stop, target, or validity values.
- Market Intelligence validation UX may summarize existing validation results,
  runs, saved symbols, eligibility, decisions, and traces. It must not invent
  unavailable reasons or outcomes.
- A validation report popup is useful from Market Intelligence surfaces, but
  not from the Decision detail panel. When the owner re-validates inside a
  selected symbol, the existing symbol detail should refresh inline instead.
- Copy must stay plain and action-oriented: enter, wait, skip, save, review,
  validate, open decision, inspect trace.

## 2. Target Experience

The owner should be able to answer these questions quickly:

1. Is the selected symbol near its entry zone now?
2. If it is not ready, should I wait, skip, or re-check?
3. Which validation stage blocked symbols today?
4. What happened after I validated a saved/universe symbol?
5. What useful action can I take next without hunting around the dashboard?

## 3. Milestone Plan

### AW-1 — Entry Readiness Indicator

**Goal:** Show whether the selected symbol's live price is inside the current
TradePlan entry zone.

Scope:

- Add a compact Decision Brief header indicator next to the live price.
- Compare existing live quote with `trade_plan.entry_low` / `entry_high`.
- Refresh the indicator whenever the live quote, selected decision, or
  authoritative plan freshness changes.
- States: `Entry ready`, `Wait for entry`, `Chasing risk`, `No current entry`,
  and `Waiting for quote`.
- Keep the chip advisory-only; it must never become an order instruction.

Acceptance:

- Expired, stale, historical, or no-plan decisions do not show an actionable
  entry state.
- A valid/aging plan with live price inside the entry zone shows `Entry ready`.
- A valid/aging plan outside the entry zone explains whether to wait or avoid
  chasing.

### AW-2 — Saved Symbol Validation and Result Report

**Goal:** Make saved symbols actionable from Market Intelligence and summarize
single-symbol validation outcomes.

Scope:

- Add a validate action to each Saved Symbols row.
- Add a validation result modal for Market Intelligence single-symbol
  validations.
- Report status, mode/time, eligibility/decision outcome, plan state when
  available, and the next useful actions.
- Opt in only from Market Intelligence callers.

Acceptance:

- Saved Symbols can be validated without moving to the Universe table.
- Decision-detail revalidation does not open the report popup; it refreshes
  inline.
- Batch/visible/full validation does not open per-symbol popups.

### AW-3 — Validation Pipeline Workbench

**Goal:** Turn Validation Pipeline from a count display into a daily-use
diagnostic workbench.

Scope:

- Revamp the main funnel card around latest run status, stage conversion,
  top blocker, and next action.
- Revamp the detail modal into useful tabs/sections: overview, blockers,
  symbols, and run history.
- Use existing funnel and pipeline-run payloads first; document any real data
  gaps before adding backend scope.

Acceptance:

- The owner can identify what blocked symbols without reading raw run payloads.
- The detail view remains useful after scoped single-symbol validations.
- No stage, blocker, or symbol detail is fabricated.

### AW-4 — Advisor Workbench Visual QA

**Goal:** Verify the complete Decisions + Market Intelligence workflow as a
production advisory cockpit.

Scope:

- Screenshot and interaction QA for Decisions, entry readiness, saved-symbol
  validation, result report, and validation pipeline.
- Regression coverage for the complete Advisor Workbench path.
- Fix layout/text issues found during QA.

Acceptance:

- No overlapping text, blocked controls, stale actionable copy, or confusing
  validation feedback remains in the reviewed workflow.

## 4. Non-Goals

- Auto-trading, broker order placement, basket creation, GTT/order draft
  generation, or OMS integration.
- New scoring, confidence, risk, decision, or TradePlan rules.
- Fabricated validation blockers, targets, exits, or symbol outcomes.

