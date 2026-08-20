# ATHENA Decision-List Confidence Design

**Milestone:** AUX-3  
**Status:** Implemented; ready for owner review  
**Authority:** Persisted ATHENA `DecisionReport` confidence assessment

## Objective

Show a compact confidence band on every Decisions-list row so the owner can
scan evidence reliability before opening a symbol. Confidence is not expected
profit, price direction, or a substitute for the Decision and TradePlan.

## Contract

- `DecisionAnalysisDTO.confidence_level` is an additive nullable field with
  the only valid values `HIGH`, `MEDIUM`, and `LOW`.
- The Decisions service reads the canonical persisted `DecisionReport` for
  the row's run. It never derives confidence from score, price, risk, or
  browser state.
- A missing report, failed report status, or unknown value projects as `null`.
  The UI renders that state as `Conf -`; it never guesses.
- Reports are loaded through a per-request run cache so a large decision board
  does not repeatedly load the same pipeline details.

## Presentation

- Each row shows `Conf High`, `Conf Med`, `Conf Low`, or `Conf -` beside its
  existing score and plan state.
- High, medium, low, and unavailable use distinct semantic tones without
  changing the row's Trade, Watch, or No trade classification.
- The control has an accessible label and the explanatory tooltip:
  `ATHENA confidence reflects evidence reliability, not expected profit.`
- Confidence remains informational. It does not sort, filter, authorize, or
  mutate a decision in AUX-3.

## Safety And Architecture

- ADR-005 remains intact: the browser renders persisted explainability data.
- Frozen analytical contracts are unchanged; the API extension is additive.
- Determinism, replayability, provider independence, and failure transparency
  are preserved.
- No order-placement path, profit claim, or browser-side classification is
  introduced. No ADR is required.

## Verification

- Service coverage verifies HIGH, MEDIUM, LOW, unavailable, report-status
  rejection, and one run-detail lookup for decisions sharing a run.
- Router coverage verifies nullable serialization.
- Dashboard hosting and release-gate coverage verifies labels, tooltip copy,
  styles, and asset cache versions.
- Full suite: **2,028 passing**. Ruff and `git diff --check` pass.
- The isolated browser reached ATHENA's owner unlock screen but did not share
  the authenticated owner session. Signed-in visual confirmation is therefore
  part of owner review, not claimed as completed automation.

## Owner Review Checklist

- Confirm all four bands are legible in the Decisions rail.
- Confirm the added pill does not truncate symbol, score, or plan-state text.
- Confirm the tooltip makes the evidence-reliability meaning clear.
- Confirm rows with unavailable confidence remain visibly honest and usable.

