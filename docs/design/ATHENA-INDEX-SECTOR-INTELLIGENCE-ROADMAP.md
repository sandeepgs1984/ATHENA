# ATHENA Index and Sector Intelligence Roadmap

**Status:** IX-3 ready for owner review on 2026-07-31  
**Scope:** Read-only broad-market and sector-index intelligence for Market
Intelligence and Decisions & Trace  
**Owner goal:** show which parts of the market are leading, then help the owner
find ATHENA-qualified symbols inside those areas without changing the approved
recommendation engines prematurely.

**Agent continuity:** read `docs/ATHENA-IX-HANDOFF.md` after verifying live
status in `docs/MILESTONES.md`, `IMPLEMENTATION_SUMMARY.md`, and git.

## 1. Product Questions

The finished experience should answer:

1. Which broad-market and sector indices are strongest or weakest now?
2. Is the displayed index information current, session-close, stale, or absent?
3. Which current ATHENA setups belong to each index?
4. Which symbols are strongest inside the selected index?
5. Is an index observation merely context, or does it affect the recommendation?

## 2. Governing Boundaries

- ATHENA remains advisory-only. This track adds no broker write path, order
  placement, basket, or execution instruction.
- Index observations are contextual until a separately approved ADR and replay
  study authorize any scoring, confidence, risk, or decision-policy influence.
- The existing benchmark index list used by validation stays separate from the
  larger quote-only display list. Expanding the display list must not multiply
  historical Kite requests during every symbol re-validation.
- Values come from the configured read-only provider and persisted ATHENA
  records. Missing levels, baselines, memberships, or breadth are reported as
  unavailable; they are never replaced with zero or estimated values.
- Constituent membership must be versioned and provenance-tagged before ATHENA
  presents index-level symbol rankings or breadth.
- Existing frozen domain objects and provider protocols remain unchanged in
  IX-1. Any later contract change is ADR-gated.
- SD-2 remains unresolved for analytical scoring. Quote-only index visibility
  does not silently activate `sector_quality`.

## 3. Data and Rate-Limit Design

ATHENA needs two explicit index sets:

- **Benchmark history set:** the small set of daily/intraday index candles
  needed by the existing regime and validation pipeline.
- **Snapshot display set:** broad-market and sector indices fetched together in
  the existing Kite quote request for dashboard intelligence.

The sets may overlap, but they have different cost and purpose. A symbol
re-validation must ingest only the benchmark history set. A market snapshot may
quote every enabled display index in one bounded request.

Every tracked index has configuration-owned identity:

- stable key;
- display label;
- provider instrument id;
- family (`broad_market` or `sectoral`);
- deterministic display order;
- enabled state.

## 4. Milestone Plan

### IX-1 — Tracked-Index Data Foundation

**Goal:** Persist and expose a trustworthy, rate-limit-safe multi-index
observation set.

Scope:

- Load quote-only snapshot indices from the separate tracked-index catalog
  while leaving the strict Kite benchmark configuration backward-compatible.
- Add a validated tracked-index catalog.
- Extend Kite market snapshots to include enabled broad-market and sector
  indices in the existing quote request.
- Add a read-only index-intelligence API returning configured order, level,
  prior-session change when a real baseline exists, data availability, source,
  and timestamp.
- Prefer persisted daily candles for prior-session change, then use the latest
  snapshot before the current trading day for quote-only display indices.
- Preserve the fixed NIFTY 50 / BANK NIFTY / VIX header ticker contract.

Acceptance:

- Adding display indices does not add historical requests to scoped symbol
  validation.
- One missing provider quote does not hide other available indices.
- Missing snapshots or prior closes produce explicit `NO_DATA` / null fields.
- Same-day snapshots are never used as the prior-session comparison baseline.
- Catalog keys and instrument ids are unique and invalid config fails loudly.
- Existing provider, ticker, and market-history tests continue to pass.
- Re-validation and selected-symbol live quotes continue to work when an
  already-running process reads the production Kite configuration.

### IX-2 — Index Leadership Surface

**Goal:** Add a compact, glanceable index-leadership surface to Market
Intelligence.

Scope:

- Present broad-market and sector groups without horizontal page overflow.
- Show level, change, observed time, and session-aware freshness.
- Highlight leaders and laggards descriptively, not as trade signals.
- Provide responsive desktop and narrow-screen layouts with accessible labels.

Acceptance:

- Closed markets say session close and next live session; connectivity is not
  mistaken for market-open state.
- Missing baselines show `Change unavailable`, never `0.00%`.
- The surface remains compact and does not displace the validation workflow.

### IX-3 — Versioned Constituents and Index Breadth

**Goal:** Connect indices to their real constituent symbols.

Scope:

- Add official, versioned constituent files with source, effective date, and
  checksum.
- Resolve constituents against ATHENA instrument ids and report unresolved
  symbols.
- Derive read-only index breadth and current-board counts from persisted
  decisions only.
- Define deterministic overlap behavior for symbols belonging to multiple
  indices.

Acceptance:

- No symbol is assigned by name guessing or sector-label approximation.
- Membership age and unresolved counts remain visible.
- Breadth is unavailable when membership or current decision data is
  incomplete.

### IX-4 — Index-Aware Discovery

**Goal:** Let the owner move from an index observation to useful ATHENA setups.

Scope:

- Add index filters to Universe, Validation Workbench Results, and Decisions.
- Add a selected-index view of current Trade, Watch, and No trade symbols.
- Rank only within existing ATHENA outcomes using current plan validity, entry
  readiness, score, confidence, risk, and freshness.
- Preserve strict symbol handoff when opening Decisions & Trace.

Acceptance:

- “Best” means best current ATHENA-qualified setup in the selected index; it
  never means largest index gain alone.
- Expired or unavailable plans cannot appear as actionable top setups.
- Filtering large lists provides immediate progress feedback and never changes
  the underlying validation result.

### IX-5 — Symbol Index Backdrop

**Goal:** Explain the selected symbol's market and index context.

Scope:

- Show relevant index membership, index direction, relative move, and current
  index breadth as a supporting Decision Brief section.
- Explain whether stock and index are aligned or diverging in plain language.
- Keep this layer informational and visibly separate from ATHENA's approved
  recommendation.

Acceptance:

- No membership or relative-strength value is shown without source data.
- The section does not duplicate the symbol header or crowd the actionable
  TradePlan fold.

### IX-6 — Evidence Review and Scoring Decision

**Goal:** Decide whether index/sector context deserves analytical influence.

Scope:

- Replay historical decisions with index observations attached.
- Measure stability, coverage, false-positive reduction, and regime dependence.
- Produce an ADR proposal covering any scoring/threshold recalibration.
- Implement no scoring change until owner approval.

Acceptance:

- Before/after decision-band movement is quantified.
- The proposal addresses SD-2/SD-3 and preserves deterministic replay.
- Rejection is a valid outcome; useful context may remain presentation-only.

## 5. Quality Gates

Every IX milestone must pass:

- focused unit and API tests;
- full-suite validation when local storage permits;
- deterministic ordering and replay behavior;
- provider rate-limit and missing-data review;
- no frozen-contract drift without ADR approval;
- no scoring or TradePlan change outside IX-6;
- no order-placement or broker write capability;
- responsive, keyboard-accessible, non-overlapping visual QA for UI milestones;
- `docs/MILESTONES.md` and `IMPLEMENTATION_SUMMARY.md` update;
- owner review before the next IX milestone starts.

## 6. Initial Tracked Set

IX-1 starts with a conservative NSE set available through the already approved
Kite read-only provider:

- Broad market: NIFTY 50, NIFTY BANK, NIFTY NEXT 50, NIFTY MIDCAP 100.
- Sectoral: NIFTY IT, NIFTY AUTO, NIFTY PHARMA, NIFTY FMCG, NIFTY METAL,
  NIFTY REALTY, NIFTY ENERGY, NIFTY PSU BANK.

Configuration owns this list so instruments can be disabled or corrected
without changing business logic.
