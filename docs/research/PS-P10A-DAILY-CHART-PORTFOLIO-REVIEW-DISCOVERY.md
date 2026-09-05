# ATHENA — PS-P10A Daily Chart Portfolio Review Intelligence Discovery

Status: proposed, not implemented
Owner input date: 2026-09-05

## Objective

Design the next My Portfolio intelligence capability so ATHENA can replace the
owner's earlier spreadsheet workflow without requiring daily manual chart
uploads.

The target experience is an automatically refreshed My Portfolio table that
uses each current holding's Kite/persisted daily chart evidence to populate the
same kind of chart-derived review fields visible in the owner's old Portfolio
Trading Snapshot:

- Status
- Conviction
- Trend / Setup
- Key Trigger
- Support 1
- Major Support / Exit
- Target 1
- Target 2
- Target 3
- Next Action
- Last Review

## Owner Evidence Supplied

1. `/Users/cbz-sandeep/Downloads/holdings.csv`
   - Current Kite-style holdings export with 20 symbols and live holding math
     columns: Instrument, Qty., Avg. cost, LTP, Invested, Cur. val, P&L, Net
     chg., Day chg.
2. `/Users/cbz-sandeep/Downloads/Stocks_Holdings_Statement.xlsx`
   - Broker holdings statement dated 04-09-2026 with 23 stock rows and
     broker-side stock name, ISIN, quantity, average buy price, buy value,
     closing price, closing value, and unrealized P&L.
3. Owner screenshots of the previous Google Sheet Portfolio Trading Snapshot.
   - The screenshots show a manually maintained spreadsheet interface, but the
     owner clarified that another agent generated the review fields from daily
     charts, not from manual typing.
4. Daily chart screenshots for examples including JINDWORLD, RAINBOW,
   RATNAVEER, and CHENNPETRO.
   - The screenshots show TradingView-style D1 candles with Volume,
     SuperTrend 10 3, and RSI 14. These are examples of expected evidence, not
     a production input source for ATHENA.

## Current ATHENA Capability

ATHENA already has:

- confirmed My Portfolio holdings import and reconciliation;
- Portfolio Sync over current holdings;
- server-owned valuation math;
- latest D1 candle price and timestamp per holding;
- persisted D1 candle access via `SqliteRepository.list_candles_recent(...,
  Timeframe.D1, as_of=...)`;
- indicator engine support for SMA, EMA, RSI, ATR, MACD, ADX, Volume MA, and
  VWAP;
- PS-P8C D1 Trend adapter using the approved SMA20/SMA50 structure rule;
- PS-P9D Opening Range Setup adapter using persisted canonical M5 and
  `OpeningRangeEngine`;
- existing 20-column Portfolio Snapshot DTO fields for the target output.

ATHENA does not yet have:

- a versioned SuperTrend indicator implementation;
- chart swing-high/swing-low extraction;
- support/resistance zone extraction;
- target-zone derivation;
- chart-derived portfolio status taxonomy such as `HOLD STRONG`,
  `REVIEW / HOLD TIGHT`, or `HOLD`;
- numeric chart-review conviction scores comparable to the old spreadsheet;
- owner-approved prose templates for key trigger and next action.

## Critical Requirement

PS-P10 must derive review fields from Kite/persisted market data. It must not
require the owner to upload daily chart screenshots. Screenshots are acceptance
examples only.

Production data path:

confirmed current holdings
-> symbol/instrument resolution
-> Kite/canonical D1 refresh for those holdings
-> persisted D1 OHLCV evidence
-> versioned indicator/evidence adapters
-> Portfolio Review adapter
-> Portfolio interpreter/snapshot
-> existing My Portfolio table

## Proposed Milestone Split

### PS-P10A — Discovery and Methodology Proposal

Audit the old spreadsheet output, attached holdings files, existing ATHENA D1
data/indicator code, and daily chart examples. Produce a frozen methodology
proposal before implementation.

Acceptance:

- Field-by-field parity map from spreadsheet to ATHENA.
- Evidence inventory naming which fields can be generated now and which require
  new approved evidence.
- Explicit null/unavailable semantics for every field.
- Proposed status taxonomy and next-action language.
- Deterministic replay plan using persisted D1 candles.
- Kite canary plan for refreshing only current holdings before any expensive
  data run.

### PS-P10B — Daily Chart Evidence Foundation

Add only the reusable evidence needed by PS-P10:

- versioned SuperTrend 10,3 measurement;
- RSI14 value and band evidence;
- volume expansion/compression evidence;
- recent swing high/low extraction;
- recent resistance/support zone extraction;
- current close relation to SuperTrend and extracted levels.

Acceptance:

- Pure functions over candle sequences.
- No Portfolio interpretation yet.
- No trading actions.
- Point-in-time `as_of` safety.
- Tests for insufficient history, stale/incoherent candles, trend flips, and
  screenshot-like examples.

### PS-P10C — Portfolio Review Methodology Freeze

Freeze how the chart evidence maps to owner-facing fields.

Candidate taxonomy to evaluate:

- `HOLD STRONG`
- `HOLD`
- `REVIEW / HOLD TIGHT`
- `WATCH`
- `EXIT RISK`
- `UNAVAILABLE`

Candidate field rules to freeze:

- Trend / Setup narrative from trend direction, price vs SuperTrend, recent
  breakout/reclaim/pullback/consolidation, RSI band, and volume evidence.
- Key Trigger from nearest meaningful reclaim/breakout/resistance level.
- Support 1 from nearest structural support or active SuperTrend support.
- Major Support / Exit from invalidation support, SuperTrend breakdown, or
  prior structural floor.
- Target 1/2/3 from prior resistance/swing/ATH extension rules only after
  owner-approved methodology.
- Next Action prose from status, profit cushion, current price vs support,
  trigger proximity, and invalidation risk.
- Numeric conviction from chart evidence only if owner approves a score formula;
  otherwise keep categorical confidence separate.

Acceptance:

- No fabricated levels.
- Every value has evidence/provenance.
- Null beats invented text when evidence is insufficient.
- No automatic ADD/EXIT/order behavior.
- No coupling to PS-P9D Setup, DecisionType, EntryQualification, or TradePlan
  unless explicitly approved.

### PS-P10D — My Portfolio Review Adapter Implementation

Implement the frozen PS-P10C methodology.

Expected implementation shape:

- `PortfolioReviewEvidence` typed value object.
- `PortfolioReviewAdapter` reading persisted D1 evidence only.
- Portfolio Sync wiring beside existing Confidence/Trend/Setup adapters.
- Existing My Portfolio 20-column contract reused where possible.
- Snapshot version bumped to the next approved interpretation version.
- Dashboard renders richer values with concise visible text and tooltip/detail
  provenance.

Acceptance:

- Focused adapter tests for chart patterns from owner examples.
- Sync tests proving all target columns populate when evidence is available.
- API/dashboard tests proving no schema break unless owner approves one.
- Real-provider canary for current holdings D1 refresh before any larger run.

## Field Parity Map

| Spreadsheet field | Current ATHENA state | PS-P10 target |
|---|---|---|
| Symbol | Available from holdings import | Keep |
| Qty | Available from holdings import | Keep |
| Avg Price | Available from holdings import | Keep |
| Last Price | Available from latest D1/quote | Keep, prefer accepted Sync price |
| Price As Of | Available | Keep |
| Investment | Available | Keep |
| Current Value | Available | Keep |
| P&L | Available | Keep |
| P&L % | Available | Keep |
| Status | Current PS-P5B status, not spreadsheet-equivalent | Add chart-review status methodology |
| Conviction | Current HIGH/MEDIUM/LOW from Decision confidence | Decide whether to add chart-review numeric conviction |
| Trend / Setup | Current SMA trend plus PS-P9D OR setup | Add richer D1 chart narrative |
| Key Trigger | Mostly unavailable unless TradePlan active | Add chart-derived trigger level/text |
| Support 1 | Deferred | Add chart-derived support |
| Major Support / Exit | TradePlan stop only when active | Add chart-derived invalidation/exit support |
| Target 1 | TradePlan target only when active | Add chart-derived target when approved |
| Target 2 | Deferred | Add chart-derived target when approved |
| Target 3 | Deferred | Add chart-derived target when approved |
| Next Action | Current HOLD/WATCH/ADD/EXIT taxonomy | Add owner-style portfolio review prose |
| Last Review | Available | Keep as Sync/review timestamp |

## Architecture Guardrails

- Do not change PS-P9D Opening Range Setup semantics.
- Do not duplicate `OpeningRangeEngine`.
- Do not use chart screenshots as production input.
- Do not call external providers from pure interpretation code.
- Do not introduce order-placement or broker-trade execution.
- Do not infer corporate-action-adjusted levels unless the D1 source is already
  approved for that purpose.
- Do not backfill historical Portfolio snapshots.
- Do not overwrite v0/v1/v2/v3 snapshots.
- Do not convert `BREAKOUT` into `ADD` or `BREAKDOWN` into `EXIT`.

## Open Owner Decisions

1. Should PS-P10 status replace the existing Status column, or should the UI
   distinguish `Portfolio Status` from `Chart Review Status`?
2. Should conviction remain categorical (`HIGH/MEDIUM/LOW`) or become a
   spreadsheet-style numeric score?
3. Is SuperTrend 10,3 the mandatory source for support/exit methodology?
4. Should target derivation stop at observed resistance/swing levels, or may it
   use ATH/extension rules when price is in blue-sky territory?
5. Should `Next Action` remain terse enough for the table, with a detail drawer
   for the full explanation, or should the table cell itself carry multi-line
   prose like the Google Sheet?

## Recommended Owner Decision

Proceed with PS-P10A discovery only after PS-P9D.1 is reviewed/frozen. Then
implement in the split above. This preserves milestone discipline while moving
directly toward the spreadsheet-equivalent My Portfolio outcome the owner wants.
