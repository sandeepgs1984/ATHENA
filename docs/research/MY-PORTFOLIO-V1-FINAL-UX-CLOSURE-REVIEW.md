# My Portfolio — Final Product-Gap / UX Closure Review

**Status:** Bounded product/UX review — NO implementation performed.
**Date:** 2026-09-05
**Scope:** My Portfolio dashboard presentation only, after PS-P10D.
**Does NOT reopen:** PS-P10C, PS-P10C.1, `portfolio-daily-review-v0` methodology,
structural-level methodology, SuperTrend methodology, or any frozen Decision /
EntryQualification / TradePlan / Interpretation semantics.

This document answers one question only: *given everything ATHENA already
computes today, what is the best final My Portfolio owner experience without
inventing new technical-analysis methodology?*

---

## 1. Deployed-Product Diagnosis

The live 22-column table (`src/athena/api/static/index.html:656-680`,
`.my-portfolio-wide-table`, `min-width: 3820px`) renders every row through
`renderMyPortfolioSnapshotRows` in
[08b-my-portfolio.js:470-497](src/athena/api/static/js/08b-my-portfolio.js:470).
Inspecting the actual population logic in
[interpretation.py](src/athena/portfolio/interpretation.py) and
[sync.py](src/athena/portfolio/sync.py) confirms the owner's observation
precisely:

| Column | Real population behavior | Source |
|---|---|---|
| Support 1 | **Hardcoded `None` unconditionally, every row, forever** | `interpretation.py:179` returns `support_1=None`; `sync.py:412` unconditionally appends `"support_1"` to `unavailable` |
| Target 2 | **Hardcoded `None` unconditionally, every row, forever** | `interpretation.py:180-181` |
| Target 3 | **Hardcoded `None` unconditionally, every row, forever** | `interpretation.py:181` |
| Major Support / Exit | Populated only when a `TradePlan` is active (`decision.trade_plan.stop_loss`) | `interpretation.py:163-167` — only TRADE-type Decisions with a live plan carry this |
| Target 1 | Populated only when a `TradePlan` is active | `sync.py:403-409` — `decision.trade_plan.targets[0]` |
| Key Trigger | Populated only pre-entry (price still below `TradePlan.entry_low`); becomes `None` the instant the trigger is "consumed" | `interpretation.py:334-347` |

Since My Portfolio holdings are, by definition, **already-owned positions**,
the entry trigger has almost always already fired (`ENTRY_TRIGGER_CONSUMED`),
and most holdings will never again carry a `TRADE`-type Decision with a fresh
`TradePlan` unless ATHENA re-signals an ADD. `Support 1` / `Target 2` /
`Target 3` are not merely "frequently empty" — they are **architecturally
incapable of ever being populated in v0** (PS-P10C.1's own frozen NO-GO).

The result matches the owner's diagnosis exactly: 5 of 22 columns (roughly
900px of the 3820px table) are either permanently or near-permanently empty,
producing a very wide table with long horizontal scrolling and heavy visual
noise for information that methodology intentionally cannot supply.

Separately, `Daily Guidance` (`myPortfolioDailyGuidanceCell`,
[08b-my-portfolio.js:268](src/athena/api/static/js/08b-my-portfolio.js:268))
only ever emits one of a small fixed set of sentences from
[daily_review.py `_guidance`](src/athena/portfolio/daily_review.py:271-303) —
3 status-driven strings plus 3 unavailability strings, 6 total. Every holding
sharing a `review_status` shows byte-identical guidance text, which reads as
repetitive across a real multi-holding portfolio, and — because the column is
260px wide and permanently visible — competes for the same scanning attention
as `Daily Review`'s own status pill immediately to its left.

---

## 2. Current Intelligence Inventory

Audited `PortfolioSnapshotRowDTO`
([portfolio.py:272-299](src/athena/api/v1/dtos/portfolio.py:272)),
`PortfolioAnalysisProvenanceDTO`
([portfolio.py:228-247](src/athena/api/v1/dtos/portfolio.py:228)),
`PortfolioDailyReviewDTO`
([portfolio.py:249-269](src/athena/api/v1/dtos/portfolio.py:249)), and the
adapters that feed them
([interpretation.py](src/athena/portfolio/interpretation.py),
[trend_adapter.py](src/athena/portfolio/trend_adapter.py),
[setup_adapter.py](src/athena/portfolio/setup_adapter.py),
[daily_review.py](src/athena/portfolio/daily_review.py)).

| Evidence | Currently computed? | Currently in DTO? | Currently rendered? | Classification |
|---|---|---|---|---|
| Valuation (qty/avg/last/investment/current value) | Yes | Yes | Yes (main table) | MAIN TABLE (unchanged) |
| P&L / P&L % | Yes | Yes | Yes (main table) | MAIN TABLE (unchanged) |
| Portfolio Status | Yes | Yes | Yes (pill, main table) | MAIN TABLE (unchanged) |
| Conviction | Yes | Yes | Yes (main table) | MAIN TABLE (unchanged) |
| D1 Trend | Yes | Yes (`trend_setup` composite string) | Yes, folded into one string with Setup | MAIN TABLE (unchanged) |
| OR Setup | Yes | Yes (same composite string) | Yes, folded into `Trend / Setup` | MAIN TABLE (unchanged) |
| Daily Review status | Yes | Yes | Yes (pill) | MAIN TABLE (unchanged) |
| Daily Guidance (frozen sentence) | Yes | Yes | Yes (own 260px column) | **DETAIL VIEW** (repetitive at main-table density; full text still valuable) |
| SuperTrend direction | Yes | Yes (`daily_review.supertrend_direction`) | Only inside a `title=` tooltip | **MAIN TABLE** (compose into concise summary) / DETAIL VIEW (full) |
| SuperTrend value | Yes | Yes (`daily_review.supertrend_value`) | Only inside tooltip | DETAIL VIEW |
| Price relative to SuperTrend | Derivable (`latest_close` vs `supertrend`, both in DTO) | Derivable, not itself a field | Not rendered | DETAIL VIEW (compose, no new methodology — same comparison `daily_review.py:126-131` already makes) |
| Raw RSI14 | Yes | Yes (`daily_review.rsi14`) | Only inside tooltip | DETAIL VIEW (context only, per frozen decision) |
| Raw Volume | Yes | Yes (`daily_review.volume`) | Only inside tooltip | DETAIL VIEW |
| Volume MA20 | Yes | Yes (`daily_review.volume_ma20`) | Only inside tooltip | DETAIL VIEW |
| Available-history-high relationship | Yes | Yes (`latest_high_exceeds_prior_available_high`) | Only inside tooltip, and only when `true` | DETAIL VIEW |
| Rolling-high relationship | Computed in `AthRollingHighEvidence` (`daily_chart_evidence.py:104-121`) but **not passed into `PortfolioDailyReviewResult`/DTO at all** | **NOT AVAILABLE** (computed, discarded before the DTO boundary) | No | **HIDDEN/INTERNAL today — a genuine "computed but not exposed" gap** (see §6, Category D) |
| Decision (type/gates) | Yes | Folded into `status`/reason codes only | Yes, via Status pill tooltip | MAIN TABLE (status) / DETAIL VIEW (raw Decision type + gate detail) |
| EntryQualification | Yes | Folded into `status`/`next_action` reasoning only | No raw field rendered | DETAIL VIEW (state + reason, owner-readable) |
| TradePlan (entry/stop/targets/validity) | Yes when active | Partially (`target_1`, `major_support_exit`) | Yes (2 of the fields) | MAIN TABLE only when populated (Target 1, Major Support/Exit) — see §3 |
| Key Trigger (genuinely available) | Yes | Yes | Yes | **MAIN TABLE, but only when populated** — see §3 |
| ADD / EXIT state | Yes (`next_action`) | Yes | Yes (pill) | MAIN TABLE (unchanged) |
| Freshness / session provenance | Yes | Yes (`PortfolioFreshnessDTO`, `provenance`) | Partial (Price As Of, Last Review only) | MAIN TABLE (as-of timestamps) / DETAIL VIEW (full provenance chain) |
| Support 1 / Target 2 / Target 3 | **Never computed — frozen NO-GO** | Field exists, always `null` | Yes (permanent dash column) | **HIDE FOR v0** (§3, disposition D) |

**Key finding:** nearly everything the owner is asking for in Task 3/4 is
**already computed and already sitting in the row's `daily_review` object or
`provenance.interpretation_evidence` blob** — it is a presentation gap, not a
data or methodology gap, with one narrow exception (rolling-high relationship,
computed then discarded — Category D in §6).

---

## 3. 20-Column Disposition Matrix

| # | Original Excel column | Disposition | Rationale |
|---|---|---|---|
| 1 | Symbol | **A** — keep permanently | Primary row identity; already sticky-positioned |
| 2 | Qty | **A** — keep permanently | Core position fact |
| 3 | Avg Price | **A** — keep permanently | Core position fact |
| 4 | Last Price | **A** — keep permanently | Core valuation input |
| 5 | Price As Of | **B** — move to detail | Freshness metadata, not a scanning field; still shown as a small inline timestamp badge is acceptable but doesn't need a full 210px column |
| 6 | Investment | **A** — keep permanently | Core valuation input |
| 7 | Current Value | **A** — keep permanently | Core valuation input |
| 8 | P&L | **A** — keep permanently | Primary owner concern |
| 9 | P&L % | **A** — keep permanently | Primary owner concern |
| 10 | Status | **A** — keep permanently | Already the ATHENA-computed health signal |
| 11 | Conviction | **A** — keep permanently | Already computed, compact |
| 12 | Trend / Setup | **A** — keep permanently | Already computed, compact |
| 13 | Key Trigger | **C** — keep only when populated | Genuinely available a minority of the time (pre-entry only); a permanent 220px column for a field null on almost every already-owned holding is the single largest structural contributor to the "empty columns" complaint alongside Support 1/Target 2/Target 3 |
| 14 | Support 1 | **D** — hide for v0 | PS-P10C.1 frozen NO-GO; never populated; do not reopen methodology |
| 15 | Major Support / Exit | **C** — keep only when populated | Real evidence (TradePlan stop) when a TRADE plan is active; otherwise legitimately absent |
| 16 | Target 1 | **C** — keep only when populated | Real evidence (TradePlan target) when active |
| 17 | Target 2 | **D** — hide for v0 | Frozen NO-GO; never populated |
| 18 | Target 3 | **D** — hide for v0 | Frozen NO-GO; never populated |
| 19 | Next Action | **A** — keep permanently | Primary owner-facing directive |
| 20 | Last Review | **B** — move to detail | Freshness metadata; useful in detail view, not primary scanning column |

Two columns exist in the deployed table beyond the original 20 (`Daily
Review`, `Daily Guidance`, PS-P10D additions):

| Column | Disposition | Rationale |
|---|---|---|
| Daily Review (status pill) | **A** — keep permanently | Frozen classification; compact pill, high scanning value |
| Daily Guidance (full sentence) | **B** — move to detail; replace main-table cell with a short composed summary (Task 3) | Full frozen guidance text stays owner-readable, just not at main-table density |

**Net effect on the main table:** of 22 current columns, **13 stay
permanently** (Symbol, Qty, Avg Price, Last Price, Investment, Current Value,
P&L, P&L%, Status, Conviction, Trend/Setup, Daily Review, Next Action), **3
become conditional/compact** (Key Trigger, Major Support/Exit, Target 1 — kept
but collapsed into a single "Levels" cell that renders "—" compactly rather
than three separate wide dash columns, or shown only when at least one is
non-null for that row), **2 move to detail** (Price As Of, Last Review — as a
single "freshness" affordance), **1 is replaced with a composed short summary**
(Daily Guidance → concise line, full text in detail), and **2 are dropped from
the main table for v0** (Support 1, Target 2, Target 3 collapse into a single
compact indicator or disappear entirely from the row — see §4).

This is expected to reduce `min-width` meaningfully below the current 3820px
— the exact number depends on the implementation milestone's actual column
design (§8) and is not fixed here.

---

## 4. Proposed Main-Table Design

Target column set (left to right), all using ALREADY-COMPUTED evidence:

1. **Symbol** (sticky)
2. **Qty** (sticky)
3. **Avg Price** (sticky)
4. **Last Price**
5. **Investment**
6. **Current Value**
7. **P&L**
8. **P&L %**
9. **Status** (pill, unchanged)
10. **Conviction** (unchanged)
11. **Trend / Setup** (unchanged)
12. **Daily Review** — pill (unchanged classification) **plus** a short
    composed one-line summary directly under/beside the pill, e.g.:
    - `HOLD` → "Bullish ST · D1 uptrend"
    - `REVIEW / HOLD TIGHT` → "Bearish ST · D1 downtrend"
    - `HOLD_STRONG` → "Bullish ST · new high"
    - unavailable → "D1 evidence unavailable" / "D1 evidence stale"

    This is a **pure composition** of fields already in the row:
    `daily_review.supertrend_direction` + `trend_setup`'s trend half (already
    parsed apart in `myPortfolioTrendCell`, [08b-my-portfolio.js:221](
    src/athena/api/static/js/08b-my-portfolio.js:221)) + the "new high" flag
    already at `daily_review.latest_high_exceeds_prior_available_high`. No
    frozen classification changes; the composition function lives in the
    dashboard JS only, mirroring how `myPortfolioTrendCell` already composes
    `Trend / Setup` from two evidence sources today.
13. **Next Action** (unchanged)
14. **Levels** (new compact composite, replacing the current 5 separate
    Key Trigger / Support 1 / Major Support-Exit / Target 1/2/3 columns): a
    single cell showing only the levels that are genuinely populated for that
    row (Key Trigger, Major Support/Exit, Target 1), each on its own short
    line with a label, e.g.:
    ```
    Trigger ₹412.50
    Exit ₹380.00
    T1 ₹455.00
    ```
    A row with none of the three populated shows a single muted "No active
    plan levels" line instead of three stacked dashes. Support 1/Target 2/3
    are never referenced here (Category D, hidden entirely for v0).
15. **Freshness** (compact, replacing Price As Of + Last Review as two
    separate 210px columns): one small right-aligned timestamp/icon showing
    price-as-of, expandable via the detail drawer for the full freshness
    chain (holdings_as_of, last_synced_at, market_data_through,
    decision_as_of).

No column here requires a new DTO field beyond what PS-P10D already ships;
the composition happens entirely at render time from `row.daily_review`,
`row.trend_or_setup`, `row.key_trigger`, `row.major_support_exit`,
`row.target_1`, and `row.freshness`/`row.price_as_of`/`row.last_review`.

---

## 5. Proposed Holding-Detail Design

A row click opens a compact drawer/panel (reusing whatever detail-panel
pattern the dashboard already uses elsewhere, e.g. the Decision chart modal
shell) with four sections, using fields **already present** in
`PortfolioSnapshotRowDTO` / `PortfolioAnalysisProvenanceDTO` /
`PortfolioDailyReviewDTO`:

**POSITION**
Qty · Avg Price · Last Price · Investment · Current Value · P&L · P&L%
(all already on the row — no new fetch)

**TECHNICAL STATE**
- D1 Trend (raw `UPTREND`/`DOWNTREND`/`MIXED` label, unpacked from
  `trend_or_setup`)
- Setup (raw `BREAKOUT`/`BREAKDOWN` label, same source)
- SuperTrend direction + value (`daily_review.supertrend_direction`,
  `.supertrend_value`)
- Price vs SuperTrend (composed: `last_price` vs `supertrend_value`, same
  comparison the engine itself already makes at
  [daily_review.py:126-131](src/athena/portfolio/daily_review.py:126) —
  presentation-only echo, not a new rule)
- Raw RSI14 (`daily_review.rsi14`) — labeled explicitly "context only, no
  overbought/oversold threshold" per the frozen decision
- Volume / VMA20 (`daily_review.volume`, `.volume_ma20`)
- Available-history-high relationship
  (`daily_review.latest_high_exceeds_prior_available_high`)
- Evidence session/freshness (`daily_review.as_of`, `.evidence_as_of`)

**ATHENA REVIEW**
- Daily Review status (pill, unchanged)
- Full deterministic guidance sentence (unchanged text, moved here from the
  main table)
- Reason codes rendered owner-readably: `daily_review_reason_codes` already
  exist in `provenance` — the dashboard already has a reason-code→sentence
  mapping pattern for `interpretation_reason_codes`
  (`myPortfolioReasonSummary`, [08b-my-portfolio.js:125](
  src/athena/api/static/js/08b-my-portfolio.js:125)); the same pattern
  extends to `daily_review_reason_codes` (a lookup table addition, not new
  logic)
- Existing Status (with its own reason-code tooltip, unchanged)
- Existing Conviction (unchanged)
- Existing Next Action (unchanged)

**LEVELS / PLAN**
- Key Trigger if genuinely available, else "Not available — no active
  pre-entry TradePlan trigger"
- Major Support / Exit if genuinely available, else "Not available — no
  active TradePlan stop"
- Target 1 if genuinely available, else "Not available — no active
  TradePlan target"
- Support 1 / Target 2 / Target 3: **always** rendered as one explicit line
  — "Support 1, Target 2, and Target 3 are not available under the current
  v0 methodology (PS-P10C.1)" — never as blank/dash cells

This satisfies Task 4's explicit instruction not to show five permanent
dashes anywhere: the main table drops them, and the detail view states the
NO-GO once, in words, rather than as silent blanks.

---

## 6. Excel-Parity Matrix

| Old Excel capability | Current ATHENA | Can improve using existing data? | Requires new methodology? | Proposed UI location |
|---|---|---|---|---|
| Trend health | D1 Trend (SMA20/50 structure) | Yes — surface raw UPTREND/DOWNTREND label directly, not only folded into a slash-string | No | Main table (Trend/Setup) + Detail |
| Momentum context | RSI14 raw | Yes — expose plainly labeled "context only" | No (explicitly forbidden to add thresholds) | Detail only |
| SuperTrend | SuperTrend 10,3 direction + value | Yes — compose into Daily Review's short summary | No | Main table (composed summary) + Detail (raw) |
| Position profit/loss context | P&L / P&L % already shown; Daily Review reason codes note profit/loss context | Yes — reason codes already exist (`PROFIT_CUSHION_PROTECT_WINNER_CONTEXT`, `LOSS_CONTEXT_REVIEW_DISCIPLINE`), just not owner-readably rendered anywhere | No | Detail (reason-code sentence) |
| Trigger | Key Trigger (pre-entry TradePlan only) | Yes — collapse to compact "Levels" cell, only-when-populated | No | Main table (Levels) + Detail |
| Support | Support 1 — frozen NO-GO | No (methodology gap, not UX) | Yes (future backlog) | Explicit "not available" statement only |
| Invalidation | Major Support / Exit (TradePlan stop only) | Yes — compact display | No | Main table (Levels) + Detail |
| Targets | Target 1 (TradePlan); Target 2/3 frozen NO-GO | Partial — Target 1 yes, 2/3 no | Yes for 2/3 (future backlog) | Target 1 in Levels; 2/3 explicit "not available" |
| Hold/Review guidance | Daily Review status + frozen guidance sentence | Yes — composed short summary at main-table density, full sentence in detail | No | Main table (composed) + Detail (full) |
| Winner protection | `PROFIT_CUSHION_PROTECT_WINNER_CONTEXT` reason code already computed | Yes — surface in detail | No | Detail |
| Deterioration warning | REVIEW_HOLD_TIGHT status + bearish SuperTrend reason | Yes — already the frozen v0 answer to this | No | Main table (Daily Review pill + composed summary) |
| Daily review freshness | `daily_review.as_of` / `evidence_as_of` | Yes — already computed, just not shown | No | Detail (Technical State freshness line) |

**Nothing in this matrix requires new methodology.** Every row that currently
reads "Can improve using existing data? Yes" is a pure presentation/plumbing
change against fields the codebase already produces.

---

## 7. Data vs Methodology vs UX Gap Classification

**A. DATA GAP** (evidence genuinely does not exist anywhere yet):
- None identified for the fields this review covers. (Structural
  support/target methodology is a *methodology* gap, not a data gap — see B.)

**B. METHODOLOGY GAP** (PS-P10C.1's frozen, deliberate NO-GO — out of scope
here, future backlog only):
- Support 1
- Major Structural Support / Invalidation beyond TradePlan stop
- Target 2 / Target 3
- Structural Review Trigger
- `EXIT_RISK`
- Numeric Review Conviction

**C. PRESENTATION/UX GAP** (the actual subject of this review):
- 5 permanently/near-permanently empty columns consuming ~900px of table
  width with no owner-facing explanation of *why* they're empty
- Daily Guidance's frozen sentence shown at full length, at main-table
  density, repeated verbatim across every row sharing a status
  — better as a short composed summary + detail expansion
- SuperTrend value/direction, raw RSI14, raw Volume/VMA20, and
  available-history-high relationship all computed and already in the DTO,
  but visible only via HTML `title=` hover tooltips (undiscoverable, not
  screen-reader-friendly, not usable on touch) rather than a real detail view
- Reason codes for Daily Review (`daily_review_reason_codes`) are persisted
  and returned by the API but have **no** dashboard-side label mapping at
  all (unlike `interpretation_reason_codes`, which already has one) — a pure
  UX/plumbing gap
- No visual distinction today between "this field is null because
  methodology forbids it" (Support 1/T2/T3) and "this field is null because
  evidence happens to be temporarily unavailable" (e.g. stale D1 session) —
  both currently render as an identical dash

**D. ALREADY SOLVED BUT NOT EXPOSED** (computed somewhere, discarded or
buried before reaching the owner):
- Rolling-high relationship (`AthRollingHighEvidence.latest_high_exceeds_
  prior_rolling`, `.prior_rolling_high`, computed in
  [daily_chart_evidence.py:104-121](
  src/athena/portfolio/daily_chart_evidence.py:104) with a live
  `rolling_sessions=50` call from `sync.py:697`) is computed for every
  holding every sync but **never passed into `PortfolioDailyReviewResult`,
  the DTO, or the dashboard** — only the *available-history* high variant
  survives to the API. This is a genuine "computed but not exposed" instance
  distinct from the Excel-parity items above; it is not required for the
  bounded milestone below and is called out here only so it isn't
  mistakenly reintroduced later as a "new methodology" ask when it already
  exists.
- Raw D1 SMA20/SMA50 values and OR15/OR30 formation detail are computed
  (`trend_adapter.py`, `setup_adapter.py`) and even reach
  `provenance.interpretation_evidence` as JSON, but are not rendered
  anywhere in the UI, tooltip or otherwise.

---

## 8. Final Bounded Implementation Plan

**One milestone, presentation/composition only. No DTO schema change, no new
methodology, no repository/service logic change.**

### Scope
1. Dashboard-only column redesign of the My Portfolio main table per §4:
   collapse Key Trigger/Support 1/Major Support-Exit/Target 1/2/3 into one
   "Levels" cell (populated-only sub-lines, Support 1/T2/T3 never
   referenced); collapse Price As Of/Last Review into one "Freshness" cell;
   replace the Daily Guidance column with a short composed summary under the
   Daily Review pill.
2. New holding-detail drawer/panel per §5, opened on row click, reusing an
   existing modal/drawer pattern already in the codebase (`api/static/js/`
   already has a chart-modal shell to model this on).
3. Extend the existing reason-code→sentence lookup pattern
   (`myPortfolioReasonSummary`) to also cover `daily_review_reason_codes`.
4. Explicit, worded "not available under v0 methodology" line for Support
   1/Target 2/Target 3 inside the detail view (never a blank cell anywhere).

### Files likely affected
- `src/athena/api/static/js/08b-my-portfolio.js` — new composition
  functions (`myPortfolioLevelsCell`, `myPortfolioFreshnessCell`,
  `myPortfolioDailyReviewSummary`, detail-drawer render function), reason
  lookup table extension
- `src/athena/api/static/css/05b-my-portfolio.css` — new column widths for
  the collapsed cells, detail-drawer styling
- `src/athena/api/static/index.html` — updated `<thead>`/`<col>` markup for
  the reduced column count; new drawer container markup; dashboard version
  bump (`?v=`) per the standing convention
- `tests/api/platform/test_dashboard_hosting.py` — updated column-header
  assertions; new assertions for the composed cells and detail drawer
  content
- `tests/api/platform/test_decision_chart_release_gate.py` — version-string
  assertion update only, if the release-gate check touches this table

### DTO changes
**None required.** Every field referenced in §4/§5 already exists in
`PortfolioSnapshotRowDTO`, `PortfolioDailyReviewDTO`, and
`PortfolioAnalysisProvenanceDTO`. (Rolling-high relationship from §7-D is
explicitly OUT of this milestone's scope — no DTO change for it here.)

### No-go boundaries (restated from the owner's hard boundaries)
Do NOT: populate Support 1; populate Major Support/Exit beyond existing
TradePlan-stop logic; populate T2/T3; invent a structural Review Trigger;
implement `EXIT_RISK`; invent numeric Review Conviction; add RSI thresholds;
add pivot/zone or target methodology; touch `SuperTrendEvidence`/
`daily_review.py`'s classification logic; touch `DecisionEngine`/
`ScoringEngine`/`PortfolioInterpreter`'s frozen rules; reopen PS-P10C;
auto-create PS-P10E.

### Tests
- Dashboard hosting contract tests for the new column headers/CSS
  selectors/JS function names (mirroring the existing pattern in
  `test_dashboard_hosting.py`)
- New unit-style tests (pure JS logic if testable, or DOM-rendering
  assertions via the existing FastAPI TestClient HTML fixture pattern) for:
  - "Levels" cell shows only populated levels, in the right order, with the
    right labels
  - "Levels" cell shows the muted "no active plan levels" line when all
    three are null
  - Daily Review composed summary matches each of the 3 populated statuses
    and the 3 unavailability reasons, driven only by existing fields (no
    new classification path)
  - Detail drawer renders the explicit Support1/T2/T3 "not available"
    sentence unconditionally
  - `daily_review_reason_codes` lookup produces owner-readable text for
    every reason code currently emitted by `daily_review.py`
- No new backend/adapter/methodology tests are needed since no backend
  logic changes

### Acceptance scenarios
Use the already-accepted representative cases from PS-P10D (CHENNPETRO,
AZAD, JINDWORLD, RAINBOW, RATNAVEER, HBLENGINE) plus at least one holding
with an active TradePlan (Key Trigger/Major Support-Exit/Target 1 all
populated) and one with none, to prove the Levels cell handles both the
sparse and the fully-populated case cleanly. Screenshot the redesigned main
table at normal and mobile-emulated widths, and the detail drawer open for
one HOLD_STRONG and one REVIEW_HOLD_TIGHT holding.

### Exact completion criterion
> On opening My Portfolio, the Owner can understand portfolio health and
> identify which holdings deserve attention without horizontally scrolling
> through mostly empty columns or opening external charts.

Operationalized as: the main table's `min-width` is measurably reduced from
today's 3820px; no column in the main table is null for more than a small
minority of real holdings (Support 1/Target 2/Target 3 removed from the main
table entirely rather than counted); every holding's Daily Review carries a
distinguishing short summary (not a single repeated sentence bank of 3-6
fixed strings at main-table density); and clicking any row surfaces the full
SuperTrend/RSI/Volume/high-context/reason-code picture without leaving the
page.

---

## 9. What Will STILL Remain Unavailable Afterward

Even after this bounded milestone:
- Support 1 — still never populated (frozen NO-GO)
- Major Structural Support / Invalidation beyond a TradePlan stop — still
  unavailable
- Target 2 / Target 3 — still never populated (frozen NO-GO)
- A structural Review Trigger — still does not exist
- `EXIT_RISK` — still not implemented
- Numeric Review Conviction — still not implemented
- Any new RSI threshold, overbought/oversold classification, or RSI-driven
  guidance — still explicitly forbidden
- Any pivot/zone/support/resistance/target methodology beyond what
  PS-P10B/C/C.1/D already froze — still explicitly forbidden
- Rolling-high relationship exposure (§7-D) — still computed but not
  surfaced; a candidate for a future, separately-authorized small milestone,
  not part of this one

This milestone closes the *presentation* gap only. It does not, and cannot
under the owner's hard boundaries, close the methodology gap that PS-P10C.1
already and deliberately left open.

---

## 10. Final Product Completion Criterion

> On opening My Portfolio, the Owner can understand portfolio health and
> identify which holdings deserve attention without horizontally scrolling
> through mostly empty columns or opening external charts.

---

## Deliverable Compliance Checklist

- [x] Deployed-product diagnosis (§1)
- [x] Current intelligence inventory (§2)
- [x] 20-column disposition matrix (§3)
- [x] Proposed main-table design (§4)
- [x] Proposed holding-detail design (§5)
- [x] Excel-parity matrix (§6)
- [x] Data vs methodology vs UX gap classification (§7)
- [x] One bounded implementation recommendation (§8)
- [x] Explicit statement of what remains unavailable afterward (§9)
- [x] Final product completion criterion (§10)
- [x] No implementation performed
- [x] PS-P10C / PS-P10C.1 / Daily Review methodology / SuperTrend
      methodology not reopened
- [x] No PS-P10E created
