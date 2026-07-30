# ATHENA Intraday Advisor UX Roadmap

**Status:** approved for TP-1 start on 2026-07-30  
**Scope:** Decision Brief and Decisions & Trace workflow clarity  
**Owner goal:** make ATHENA feel like a world-class intraday advisory cockpit
without adding order placement, fabricated signals, or unreviewed architecture
changes.

## 1. Governing Boundaries

- ATHENA remains advisory-only. It never places orders, prepares broker
  baskets, or calls broker write APIs.
- The dashboard presents existing Decision, TradePlan, freshness, quote,
  candle, eligibility, score, confidence, risk, and validation data.
- UX wording may clarify the owner's manual workflow, but it must not change
  ATHENA's decision type, score, risk, confidence, or TradePlan values.
- Any future endpoint must be additive and read-only unless an approved ADR
  explicitly says otherwise.
- Every visible instruction must distinguish between:
  - current actionable plan,
  - review-only / market-closed plan,
  - stale or expired historical plan,
  - no current plan because eligibility/scoring did not produce one.
- Playbook and SOP copy must be understandable by a normal trader. Prefer
  plain words like "check again", "skip", "exit", "price", and "target" over
  internal terms such as pipeline, persisted artifact, validation cycle, or
  thesis.

## 2. Target Experience

The owner should be able to answer five questions without inference:

1. Can I act on this setup now?
2. What exact entry, stop, target, and validity window apply?
3. What must happen before I enter?
4. What do I do if entry does not trigger, stop hits, target hits, or the plan
   expires?
5. What remains manual and outside ATHENA?

## 3. Milestone Plan

### TP-1 — Trade Playbook Foundation

**Goal:** Make the selected symbol's manual trading workflow explicit.

Scope:

- Move symbol-specific `Re-validate` out of the generic header actions and into
  Advisor Status, where stale/expired/not-actionable messages already live.
- Add a Trading Steps panel to the Decision Brief setup tab.
- Spell out entry, stop, target, no-fill, expiry, market-close, and
  revalidation rules in plain language.
- Keep every step conditional on existing plan/session/freshness state.
- No order placement, no broker write behavior, no strategy/scoring changes.

Acceptance:

- The header keeps only display/system actions; symbol revalidation is
  contextual inside Advisor Status.
- The playbook is visible before TradePlan levels in the setup tab.
- Expired/historical plans tell the owner not to use old entry/stop/target
  levels.
- Valid plans still state that ATHENA is advisory and manual confirmation is
  required.

### TP-2 — Current Board Controls

**Goal:** Improve the left Decisions board as a live work queue.

Scope:

- Add `Re-validate Visible` to re-run scoped validation for currently visible
  board symbols.
- Show a blocking progress state and a result summary.
- Keep after-hours wording in review/session-close mode.
- Do not revalidate hidden historical expired plans.

Acceptance:

- The button validates only visible current-board symbols.
- The user sees symbol count and the final Trade/Watch/No trade/Excluded
  summary.
- Failed validation does not silently leave stale rows looking actionable.

### TP-3 — Top Current Setups

**Goal:** Give the owner a high-signal starting point for the trading day.

Scope:

- Add a `Top Current Setups` section above the normal Trade/Watch/No trade
  groups.
- Include only current valid/aging TradePlans from eligible/latest decisions.
- Sort by score, confidence, risk, then expected-return/R:R using already
  available values.
- Cap at 10 rows.

Acceptance:

- No expired/stale/no-plan/excluded rows appear in Top Current Setups.
- The section title avoids promising "best trades"; it is a ranked review
  queue, not a guarantee.

### TP-4 — Intraday SOP Surface

**Goal:** Provide a persistent, non-symbol-specific operating manual.

Scope:

- Add an intraday SOP view or help modal from Decisions & Trace / Operations.
- Document how ATHENA should be used during pre-open, live market, and
  post-market review.
- Include end-of-day handling rules and manual broker execution boundaries.

Acceptance:

- The owner can reach the SOP without opening a symbol.
- The SOP makes clear that ATHENA does not place orders and does not guarantee
  outcomes.

## 4. Non-Goals

- Auto-trading, broker order placement, basket creation, GTT/order draft
  generation, or OMS integration.
- New scoring/risk/decision rules.
- New recommendations beyond the persisted ATHENA Decision.
- Fabricated targets, stop movement, trailing stops, or forced exits not
  already represented by approved policy.

## 5. Review Workflow

One TP milestone is implemented and reviewed at a time:

1. Design.
2. Implement.
3. Test.
4. Self-validate.
5. Milestone review summary.
6. Owner approval.
7. Next TP milestone.
