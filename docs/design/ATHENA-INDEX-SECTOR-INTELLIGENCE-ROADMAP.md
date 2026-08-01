# ATHENA Index and Sector Intelligence Roadmap

**Status:** IX-1 through IX-5 approved; IX-6 blocked on decision/outcome
history sufficiency (2026-08-01 feasibility check). IX-7/IX-8 (§6, Tier-1
presentation enhancements, independent of IX-6's gate) approved 2026-08-01.  
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

**Split (owner-approved 2026-08-01):** IX-4's combined scope (three dashboard
surfaces plus a new selected-index view) is too large for one review sitting.
It is split into three independently reviewable sub-milestones, each with its
own Design → Implement → Test → Self-Validate → Milestone Review Summary →
owner-approval gate. Only one is in flight at a time.

- **IX-4a** — Index members endpoint + Universe index filter
- **IX-4b** — Validation Workbench Results index filter
- **IX-4c** — Decisions index filter + selected-index Trade/Watch/No-trade view
  + strict symbol handoff

Common scope across all three:

- Add index filters to Universe, Validation Workbench Results, and Decisions.
- Add a selected-index view of current Trade, Watch, and No trade symbols.
- Rank only within existing ATHENA outcomes using current plan validity, entry
  readiness, score, confidence, risk, and freshness.
- Preserve strict symbol handoff when opening Decisions & Trace.

Acceptance (all three sub-milestones):

- “Best” means best current ATHENA-qualified setup in the selected index; it
  never means largest index gain alone.
- Expired or unavailable plans cannot appear as actionable top setups.
- Filtering large lists provides immediate progress feedback and never changes
  the underlying validation result.

#### IX-4a design — index members endpoint + Universe index filter

**Data gap found during Design:** IX-3's `/market/index-intelligence` endpoint
(`market_history_service.py::_index_constituent_contexts`) already resolves
every official constituent to at most one instrument and computes its current
Trade/Watch/No-trade bucket, but it only serializes aggregate counts
(`IndexConstituentContextDTO`) to the frontend — the actual per-symbol
`{symbol → instrument_id, bucket}` map is computed and then discarded. IX-4a
adds a read-only endpoint that serializes that same, already-computed
resolution instead of a second inferred mapping.

Backend:

- Refactor `_index_constituent_contexts` to extract its per-index resolution
  (instrument lookup + current-board bucket) into a shared private helper, so
  the new endpoint reuses the identical resolution path — no second mapping.
- Add `IndexMemberDTO` (`symbol`, `instrument_id | None`, `resolved: bool`,
  `bucket: Literal["TRADE","WATCH","NO_TRADE"] | None`) and `IndexMembersDTO`
  (`key`, `label`, `effective_date`, `members: tuple[IndexMemberDTO, ...]`) in
  `dtos/market.py`.
- Add `MarketHistoryService.index_members(index_key)` returning
  `IndexMembersDTO | None` (None when the key is unknown/disabled).
- Add `GET /market/index-intelligence/{index_key}/members`
  (`operation_id="getIndexMembers"`, `Permission.READ`), 404 via the existing
  resource-not-found pattern when the key is unknown/disabled.

Frontend (Universe tab only):

- Populate an index-filter `<select>` (mirrors the existing sector filter)
  from the already-fetched `/market/index-intelligence` catalog (key/label) —
  no new fetch needed just to list indices.
- On first selection of a given index, lazily fetch and cache its members from
  the new endpoint; disable the filter control while the fetch is in flight
  (immediate progress feedback) and reuse the cached list afterward — a purely
  client-side, presentation-only filter of the existing Universe rows via a
  new `matchesIndex` clause in `applyUniverseFilters()`, mirroring the
  existing sector-filter pattern exactly. No validation result is recomputed
  or mutated.
- Surface unresolved-symbol counts from the already-fetched
  `IndexConstituentContextDTO.unresolved_symbols`/`breadth_status` next to the
  filter so incomplete membership stays visible rather than silently dropped.

Acceptance (IX-4a specific):

- The new endpoint returns the exact same resolution IX-3 already computes —
  no name/sector/alias-based guessing, no second inferred mapping.
- An index with `INCOMPLETE_INSTRUMENTS`/`INCOMPLETE_DECISIONS` still returns
  its resolved members; the incompleteness remains visible via existing
  IX-3 fields, never silently hidden.
- Selecting an index filters Universe rows only; it does not call validation,
  mutate any row's eligibility, or change scoring/decision data.
- No frozen domain object, provider protocol, or existing IX-1/IX-2/IX-3
  contract changes.

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

## 6. Analytical-Influence Audit and Tiered Roadmap (owner direction, 2026-08-01)

The owner asked how to use ATHENA's index data to pick better intraday
setups. Before proposing anything, this section records what actually exists
today — verified directly against the code and the live database, not
assumed from earlier design docs.

### 6.1 What currently influences a Decision, and what doesn't

| System | Computes | Influences scoring/risk/decision? |
|---|---|---|
| **Regime** (`src/athena/regime/`) | Trend/volatility/gap off ONE benchmark index (Nifty 50), identical for every symbol in a cycle | **Yes** — scoring's `trend` component, risk's volatility/gap components, decision's LONG/SHORT direction |
| **Market Health / F-5** (`src/athena/market_health/`) | 6-component score (trend quality, breadth, liquidity, volatility, institutional flow, gap stability) from constituent-level data + ADR-008 FII/DII, independent of the IX track | **Yes** — scoring's `market_quality` (weight 20), risk's market-environment component |
| **Sector Health** (`src/athena/sector_health/`) | Per-sector trend/breadth/momentum/volatility from a sector index candle series | **No — built and tested, but never instantiated outside its own tests.** `sector_quality` (weight 15) is permanently `UNKNOWN` for every symbol ever scored (D-3). Confirmed: `grep SectorHealthEngine src/` finds no live call site |
| **IX track (IX-1–IX-5)** | Index catalog, single-day leadership sort, versioned membership/breadth, symbol-index same/opposite-day sign | **No, by design** — zero references from `scoring/`, `confidence/`, `risk/`, or `decision/` (confirmed by grep). Presentation-only, per §2's governing boundary |

**Why Sector Health is inert, confirmed at the database level:** it needs a
sector index candle *series* to compute trend/momentum. Querying
`candles` directly shows only three instruments have any historical rows —
`NSE:NIFTY 50`, `NSE:NIFTY BANK`, `NSE:INDIA VIX` (925 daily bars each,
matching regime's benchmark set). None of the 8 sectoral indices, nor NIFTY
NEXT 50 / NIFTY MIDCAP 100, have a single historical candle — IX-1 only ever
ingests their live snapshot level for display (§3's "snapshot display set"),
never their history. This is `SD-2` (`docs/MILESTONES.md`), already
identified and already blocked on an owner data-sourcing decision — nothing
new, just re-confirmed against current data.

### 6.2 Tiered roadmap

**Tier 1 — richer presentation, zero new data, zero ADR** (this section
registers IX-7 and IX-8 below)

Two enhancements reuse data already fetched/computed today with no backend
change:

- Make the Decision Brief's Symbol Index Backdrop (IX-5) show *how much* a
  stock is outperforming or lagging its index, not just a same/opposite-day
  sign flag.
- Make the Index Leadership card's leader/laggard summary show ATHENA's own
  decision breadth for that sector alongside its price move, so "IT is
  leading" and "IT also has 12 live TRADE setups" appear together.

**Tier 2 — the highest-leverage move available, but it is the owner's
decision (SD-2), not new work invented here**

Ingest historical candles for the 8 sector indices, the same way IX-1
already does for Nifty 50/Bank Nifty/VIX. This is infrastructure, not a
scoring change — but it is the prerequisite for Sector Health to run at all,
and per `SD-3` wiring its output into the weight-15 `sector_quality`
component still requires explicit owner approval and a before/after replay
diff, exactly as already documented. Revisiting SD-2 now that IX-1 exists may
be materially less work than when it was first raised.

**Tier 3 — real analytical use of index/sector context, gated on IX-6**

Sector-alignment as a scoring/confidence input, sector-scoped regime
(judging bank stocks against Bank Nifty instead of Nifty 50), and
sector-breadth as a market-regime-style gate. All three require IX-6's
replay study and ADR per §4's IX-6 scope, and IX-6 remains blocked on
decision/outcome history sufficiency (`docs/MILESTONES.md`, 2026-08-01
feasibility check). Nothing in Tier 3 is implemented by this section.

### IX-7 — Relative-strength Symbol Index Backdrop (approved 2026-08-01)

**Goal:** Replace IX-5's bare same/opposite-day sign comparison with a
magnitude-based relative-strength reading, using data IX-5 already has.

**Data gap found during Design: none.** `indexBackdropAlignment(stockChangePct,
indexChangePct)` (`js/15-decision-brief-context.js`) already receives both
real numbers it needs — `stockChangePct` from `activeBriefQuote.change_pct`
(already loaded for the Decision Brief header) and `indexChangePct` from
`item.change_pct` (already part of the `IndexIntelligenceItemDTO` IX-5
already fetches). No DTO change, no new endpoint, no new fetch.

Scope:

- Compute relative strength as `stockChangePct − indexChangePct` (both
  already-real numbers; `null` propagates, never a fabricated zero).
- Replace the two-bucket same/opposite label with magnitude tiers (e.g.
  "Strongly outperforming its index", "In line with its index", "Lagging its
  index" — exact thresholds and copy decided at Implement time, using round,
  clearly-labeled percentage-point bands so the reasoning is inspectable,
  never a hidden formula).
- Keep the existing "Flat move" / unavailable handling exactly as-is.

Acceptance:

- No new backend/DTO/endpoint change.
- Every existing IX-5 no-fabrication guarantee holds: unavailable inputs
  still render "unavailable," never a guessed value.
- Presentation-only — does not touch scoring, confidence, risk, or decision
  policy.

### IX-8 — Sector Leadership + Decision Breadth Combined View (approved 2026-08-01)

**Goal:** Show the leading/lagging sector's own price move next to ATHENA's
already-computed decision breadth for that sector, in the same compact card.

**Data gap found during Design: none.** `indexObservationMarkup(item,
compact)` (`js/09-market-intelligence.js`) already receives each index
item's `constituents` field (`IndexConstituentContextDTO` — `trade_count`,
`watch_count`, `no_trade_count`, `trade_breadth_pct`, `breadth_status`) as
part of the exact same `/market/index-intelligence` payload the leadership
card already renders; it is simply not read when `compact === true` (the
leader/laggard summary path). No new fetch, no new endpoint.

Scope:

- Extend `renderIndexLeadership()`'s leader/laggard summary block to show a
  compact breadth chip (e.g. "12 Trade · 34 Watch") sourced from
  `leader.constituents`/`laggard.constituents`, only when
  `breadth_status === "AVAILABLE"` — omitted (not a fabricated
  "unavailable" chip) otherwise, matching the existing compact-mode
  convention of omitting rather than padding out incomplete data.
- No change to the existing expanded broad/sector grids (they already show
  full breadth detail via `indexConstituentContextMarkup`).

Acceptance:

- No new backend/DTO/endpoint change.
- Breadth never appears fabricated or estimated; `INCOMPLETE_*` statuses stay
  silent in this compact view exactly as today's compact mode already treats
  other unavailable fields.
- Presentation-only — does not touch scoring, confidence, risk, or decision
  policy.

## 7. Initial Tracked Set

IX-1 starts with a conservative NSE set available through the already approved
Kite read-only provider:

- Broad market: NIFTY 50, NIFTY BANK, NIFTY NEXT 50, NIFTY MIDCAP 100.
- Sectoral: NIFTY IT, NIFTY AUTO, NIFTY PHARMA, NIFTY FMCG, NIFTY METAL,
  NIFTY REALTY, NIFTY ENERGY, NIFTY PSU BANK.

Configuration owns this list so instruments can be disabled or corrected
without changing business logic.
