# SI-P2E — ATHENA Decision Experience Implementation

**Date:** 2026-09-14

**Status:** COMPLETE AND FROZEN

**Asset:** `9.277.0`

## 1. Objective and verdict

SI-P2E turns the existing Symbol Intelligence ATHENA Decision tab into a
premium, evidence-first explanation of the latest persisted Decision. The
preceding discovery found the frozen SI contract sufficient, so implementation
is frontend-only. No architecture, methodology, API, DTO, schema, repository,
composer or engine change was required.

## 2. Implemented information hierarchy

- A prominent persisted-Decision hero shows the human-readable type and any
  persisted direction as one restrained primary verdict (for example,
  `TRADE · SHORT`), plus Decision date and independent Decision freshness.
- A compact strength band admits only available persisted confidence, score,
  and a presentation count over the actual persisted gate list.
- “Decision Evidence” presents the persisted explanation without adding a
  stronger causal claim, followed by all individual gate outcomes. Failed gates
  open by default; passed-gate detail is available progressively; an absent
  persisted outcome is labelled unavailable rather than failed. Gate names are
  deterministically humanized and stored detail is never regenerated.
- A Decision-owned TradePlan section renders the exact stored entry band, stop
  loss, target list, risk/reward, position size, risk amount and validity
  bounds. It never invents Target 2/3 and never relabels stop loss as Support.
- Plan freshness is visibly separate from Decision freshness. Missing plans
  state the fact without manufacturing a setup. Missing optional numeric values
  remain absent rather than being coerced into a score or risk/reward of zero.
- `Open Decision Brief` retains the canonical
  `/dashboard/decisions?decision=<decision_id>` route. `View Evidence` retains
  the local SI audit jump.

## 3. Empty, stale and invalid states

A valid symbol with no Decision renders “No persisted decision,” explains that
Stock 360 research remains available, and offers Stock 360/Evidence navigation.
It does not offer Generate or Validate actions.

Decision freshness is read from the existing `ATHENA_DECISION` source row, not
from overall SI coverage. A stale Decision is explicitly marked beside its own
timestamp. Stale completed-D1 evidence gets a separate warning while the
persisted Decision remains visible as historical evidence. An unresolved
identity clears Decision-specific content and renders a distinct symbol-
unavailable state.

## 4. Preserved boundaries

- GET remains read-only composition; Analyze remains completed-D1 hydration
  followed by re-read.
- No DecisionEngine, validation, Decision mutation, Portfolio Sync or DarvaX
  action is invoked.
- Current SMA/SuperTrend/RSI/volume/levels, Portfolio guidance and DarvaX
  interpretation are not duplicated into the Decision tab.
- Full trace, context, resource references, dimensions, history, journal,
  outcomes, analogs and counterfactuals remain in the Decision Brief.
- SI-P1/P2A/P2B/P2C/P2D contracts and behavior remain frozen.

## 5. Responsive and accessibility behavior

Desktop uses a restrained hero, three-part strength band and a balanced
evidence/TradePlan layout. At 720px and below the surface becomes a single
normal-flow column, strength facts separate cleanly, plan values retain
tabular alignment, and actions become full-width. The SI identity header also
becomes a deliberate symbol/status → price → completed-D1 context stack; its
session facts remain visible and the four-surface navigation becomes a usable
two-column control. Gate rows are native `details` disclosures with visible
outcome text; failed details begin open. There is no fixed width or horizontal-
scroll dependency.

## 6. Deterministic coverage

Focused SI-P2E coverage executes the actual renderer and verifies:

- human Decision type/date, optional confidence and persisted score;
- the non-causal “Decision Evidence” heading, unchanged persisted explanation,
  and direction coupled to the verdict only when direction is persisted;
- actual passed/total counts, individual labels/outcomes/details and default-
  open failures;
- all-passed NO_TRADE without invented causality;
- exact TradePlan fields and one-target rendering without invented T2/T3;
- partial/malformed optional numeric omission without fabricated zeroes, plus
  explicit unavailable-gate presentation;
- missing-plan, no-Decision and invalid-symbol states;
- independent stale Decision and stale-D1 warnings;
- Decision Brief and Evidence navigation;
- absence of Stock 360, Portfolio and DarvaX evidence from the Decision
  renderer;
- preserved Analyze request boundary, responsive CSS and asset pins.

No browser screenshots were generated; the Owner may capture final evidence
manually as authorized.

Final closure validation on 2026-09-15 completed with:

- `9 passed` in the focused SI-P2E renderer contract;
- `101 passed` across Symbol Intelligence plus the impacted dashboard-hosting
  and Decision/chart release gates;
- the latest full repository result remains `4106 passed, 0 failed, 2 skipped`;
  it was not rerun because this closure changes only local presentation;
- JavaScript syntax, CSS brace balance, scoped Ruff, scoped mypy, and
  `git diff --check` all clean.

Browser geometry validation exercised PINE LABS TRADE/SHORT with EXPIRED
TradePlan, WIPRO NO TRADE, and TI no Decision at 1579px and 390px. Every state
kept symbol identity, price, completed-D1 date/close, Analyze, and all four SI
destinations visible. At 390px with the unchanged global rail in its existing
icon-only mode, both `.workspace-viewport` and `.si-workstation` reported exact
`scrollWidth === clientWidth` (318/318 and 294/294 respectively); document
overflow was also zero.

## 7. Known limitations and deferrals

The surface explains only the latest persisted Decision. Historical comparison,
raw trace, context, deep dimensions, counterfactuals, analogs and journal/
outcomes remain intentionally in the Decision Brief. Technical persisted gate
detail is shown faithfully rather than rewritten into a potentially false
narrative. A partial TradePlan is not valid under the typed contract; malformed
optional values fail closed and are never completed by the UI.

The initial Decision renderer and styling entered the committed Stock 360
baseline in `dc8f26a`. This closure does not rewrite history: it validates that
runtime in place, adds the bounded fail-closed corrections above, and records
the independently reviewable SI-P2E reports and regression contract on asset
`9.277.0`.

Final Owner visual review of `9.276.0` identified exactly three bounded
presentation issues: a causal section heading, secondary-looking Decision
direction, and narrow SI-header clipping. Asset `9.277.0` resolves them by
renaming the container to “Decision Evidence,” coupling persisted direction to
the primary verdict, and explicitly restacking the SI identity/session/navigation
layout at narrow width. No approved Decision surface or frozen contract was
redesigned.

SI-F0 and SI-N0 were not started.

## 8. Milestone stop

**SI-P2E — COMPLETE AND FROZEN on asset `9.277.0` (2026-09-15).**

Owner / Chief Architect final visual and source review passed. Do not modify
the frozen milestone or begin another Symbol Intelligence milestone without
separate approval.
