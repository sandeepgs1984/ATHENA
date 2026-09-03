# PS-P5B Portfolio Interpretation Implementation

Status: Implementation complete; ready for owner/principal-engineer review
Date: 2026-09-03
Scope: Approved PS-P5B Portfolio Interpretation subset only
Boundary: No ScoringEngine, DecisionEngine, indicator, provider, DarvaX, broker,
order-placement, or future-phase implementation changes

## 1. Objective

Implement the owner-approved PS-P5A subset as a deterministic Portfolio
Interpretation layer for My Portfolio snapshots.

## 2. Approved Inputs

The implementation consumes only current accepted Portfolio Sync evidence:
holding facts, D1 price freshness, coherent persisted `Decision`, active
coherent `TradePlan`, quality gates, and latest coherent persisted
`EntryQualification` for ADD readiness.

## 3. Non-Goals

No confidence reconstruction, trend/setup derivation, Support 1 methodology,
target ladder fabrication, P&L-based trading interpretation, DarvaX evidence,
intraday evidence parsing, order placement, or core decision methodology change
was implemented.

## 4. Architecture

`athena.portfolio.interpretation` is pure and side-effect free. Portfolio Sync
selects evidence and persists the resulting row fields, reason codes, and
provenance.

## 5. Version

All outputs use `portfolio-interpretation-v0`.

## 6. Status

Implemented status vocabulary: `STRONG`, `HEALTHY`, `CAUTION`, `AT_RISK`,
`UNAVAILABLE`. Precedence follows PS-P5B: freshness/coherency, invalidation,
insufficient/gate failures, current positive evidence, conservative fallback.

## 7. Conviction

Conviction remains null and records `CONFIDENCE_EVIDENCE_UNAVAILABLE`.

## 8. Trend Setup

Trend / Setup remains null and records `TREND_SETUP_NOT_AVAILABLE`.

## 9. Key Trigger

Key Trigger uses only active coherent `TradePlan.entry_low`: price below entry
low returns the entry-low value; price at or above entry low returns null with
`ENTRY_TRIGGER_CONSUMED`.

## 10. Support 1

Support 1 remains null and records `SUPPORT_1_METHODOLOGY_UNAVAILABLE`.

## 11. Major Support Exit

Major Support / Exit uses only active coherent `TradePlan.stop_loss`. Stale or
expired plans do not populate it.

## 12. Target 1

Target 1 remains the first active coherent TradePlan target and preserves the
PS-P4.1 same-session evidence gate.

## 13. Target 2 And 3

Target 2 and Target 3 remain null and record `NO_APPROVED_SECONDARY_TARGET`.

## 14. Next Action

Implemented vocabulary: `HOLD`, `ADD`, `EXIT`, `WATCH`. `REDUCE` and `ROTATE`
remain deferred.

## 15. ADD Rule

ADD requires current coherent price/Decision/TradePlan evidence plus latest
coherent persisted `EntryQualification` in `QUALIFIED` state for the same
instrument, session, decision, run, cycle, and decision type, not after the
interpretation timestamp.

## 16. EXIT Rule

EXIT requires an active coherent TradePlan stop breach. The boundary is
inclusive: `last_price <= stop_loss`.

## 17. HOLD Rule

HOLD is the conservative normal action when the active thesis is intact but ADD
and EXIT are not confirmed.

## 18. WATCH Rule

WATCH is used when evidence is unavailable, stale, cautionary, or insufficient
for a stronger action.

## 19. P And L Independence

The interpreter does not accept or read cost basis, unrealized P&L, or P&L
percent. Valuation math remains separate server-owned snapshot math.

## 20. Freshness Protection

Stale price or stale Decision evidence produces `UNAVAILABLE` / `WATCH` and
prevents TradePlan stop, trigger, and target leakage.

## 21. Provenance

`PortfolioAnalysisProvenance` now records interpretation version, reason codes,
and compact evidence acceptance flags.

## 22. API And Dashboard

The existing snapshot DTO now carries interpretation provenance. Dashboard row
rendering continues to consume server fields; no client-side trading logic was
added.

## 23. Tests

Added pure interpreter tests for status/action precedence, key-trigger
boundaries, stop breach equality, null methodology fields, and P&L
independence. Updated sync/API tests for row values, freshness rejection,
partial sync, active triggers, stop output, and coherent EntryQualification ADD.

## 24. Verification

Targeted verification passed:

`rtk pytest tests/runtime/test_portfolio_interpretation.py tests/api/v1/test_my_portfolio_import_api.py`

Result: 29 passed.

Full suite verification passed:

`rtk pytest`

Result: 3167 passed, 0 failed, 1 skipped.

## 25. Review Notes

PS-P5B is ready for review. Next milestone work must not begin until owner /
principal-engineer approval is received.
