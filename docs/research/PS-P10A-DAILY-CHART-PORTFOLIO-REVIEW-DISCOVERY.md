# ATHENA — PS-P10A Daily Chart Portfolio Review Intelligence Discovery

Status: discovery complete, ready for Owner/Chief Architect review
Owner authorization date: 2026-09-05

## 1. Executive Summary

PS-P10A investigated how My Portfolio can replace the owner's previous
Portfolio Trading Snapshot workflow without daily chart screenshot uploads.

The core finding: the old sheet feels more useful because it had a
chart-review interpretation layer. ATHENA has stronger infrastructure underneath
— canonical holdings, Kite/canonical market refresh, persisted D1 OHLCV,
immutable snapshots, currentness/provenance, and versioned Portfolio
interpretation — but PS-P5 through PS-P9 intentionally froze only narrow,
evidence-approved fields. ATHENA is therefore honest but sparse: it refuses to
fill Key Trigger, Support 1, Target 2/3, and rich action guidance until those
fields have deterministic chart methodology.

The target PS-P10 production path remains:

confirmed holdings -> canonical/Kite market-data refresh -> persisted D1 OHLCV
-> deterministic/versioned chart evidence -> Portfolio Review intelligence
-> immutable Portfolio snapshot -> My Portfolio dashboard

Chart screenshots are reference examples only. They must never become a
production input. The required next implementation milestone is not dashboard
polish; it is a reusable D1 chart-evidence foundation, especially SuperTrend
10,3 and structural level extraction, followed by a separate methodology freeze
before Portfolio Review fields are populated.

No production code, schema, API/DTO, dashboard behavior, interpretation version,
indicator implementation, SuperTrend implementation, support/resistance logic,
or target logic changed in PS-P10A.

## 2. Spreadsheet-vs-ATHENA Parity Matrix

Classification:

- A: already production-complete.
- B: production-complete but semantically different from the old sheet.
- C: partially populated.
- D: missing methodology/evidence.
- E: intentionally deferred under frozen semantics.

| Portfolio Snapshot field | Class | Current ATHENA state | Old-sheet behavior | Gap / PS-P10 requirement |
|---|---:|---|---|---|
| Symbol | A | Canonical holding symbol from import/resolution. | Stock symbol/name displayed. | Keep as-is. |
| Qty | A | Canonical imported quantity. | Quantity displayed. | Keep as-is. |
| Avg Price | A | Canonical imported average price. | Average price displayed. | Keep as-is. |
| Last Price | A | Latest accepted D1/sync price. | Latest chart/review price, not necessarily live feed. | Keep accepted-session semantics explicit. |
| Price As Of | A | D1 price timestamp from accepted snapshot. | Review date/close date. | Keep; label accepted session clearly. |
| Investment | A | Server-owned holding math. | Sheet formula. | Keep server-owned. |
| Current Value | A | Server-owned holding math when priced. | Sheet formula. | Keep server-owned. |
| P&L | A | Server-owned holding math when priced. | Sheet formula. | Keep server-owned. |
| P&L % | A | Server-owned holding math when priced. | Sheet formula. | Keep server-owned. |
| Status | B | Frozen Portfolio Status: STRONG/HEALTHY/CAUTION/AT_RISK/UNAVAILABLE, from PS-P5B Decision/TradePlan/currentness semantics. | Chart-review status such as HOLD STRONG, HOLD, REVIEW / HOLD TIGHT. | Do not redefine existing Status. Add a separate Daily Review status if owner approves. |
| Conviction | B | Frozen PS-P7B categorical Decision Confidence HIGH/MEDIUM/LOW. | Numeric chart-review score such as 9.2/8.8/6.9. | Do not replace Conviction. Decide whether a separate Review Score is needed. |
| Trend / Setup | C | PS-P8C D1 SMA20/SMA50 Trend plus PS-P9D OR Setup. | Rich prose: structural uptrend, consolidation, ATH, reclaim, pullback, momentum. | Add D1 chart review narrative separate from frozen Trend/Setup, or version a new Portfolio Review dimension. |
| Key Trigger | D/C | Populated only when active TradePlan trigger exists; otherwise unavailable. | Chart-derived breakout/reclaim/resistance levels. | Requires resistance/pivot/reclaim methodology. |
| Support 1 | E/D | Explicitly deferred in PS-P5B/P7/P8/P9. | Near support zone from chart/SuperTrend/structure. | Requires support-zone methodology. |
| Major Support / Exit | C/D | Active TradePlan stop when coherent; otherwise unavailable. | Structural invalidation, SuperTrend, close-below support. | Requires separation of structural review exit from TradePlan stop. |
| Target 1 | C/D | Active TradePlan target when coherent; otherwise unavailable. | Next resistance or extension level. | Requires target methodology; cannot reuse TradePlan blindly. |
| Target 2 | E/D | Deferred. | Secondary resistance/extension. | Requires target methodology. Null remains valid. |
| Target 3 | E/D | Deferred. | Higher resistance/ATH/extension. | Requires target methodology. Null remains valid. |
| Next Action | B | Frozen machine action HOLD/WATCH/ADD/EXIT from Decision/TradePlan/currentness. | Owner guidance prose: protect winner, hold while support holds, reassess if level fails. | Add separate Review Guidance; do not silently redefine machine action. |
| Last Review | A | Snapshot analyzed_at. | Sheet review date. | Keep; include evidence session in provenance. |

Why the old sheet feels more useful:

- It answers the owner's portfolio-management question directly: "What should I
  watch or protect in this holding?"
- It fills chart-derived fields with concrete levels and prose.
- It separates position management from new-entry Decision logic, even if it did
  so informally.
- It uses familiar daily-chart concepts visible to the owner: SuperTrend, RSI,
  ATH/reclaim, support, resistance, consolidation, pullback.

Why ATHENA is currently sparse:

- ATHENA has deliberately refused to fabricate levels from unfrozen methodology.
- Existing Portfolio Status/Conviction/Next Action are frozen and cannot be
  repurposed as chart-review fields in PS-P10A.
- SuperTrend 10,3 is not implemented or versioned.
- Structural support/resistance and target extraction are not implemented.

## 3. Representative Owner-Case Analysis

The examples below use the owner-provided sheet screenshots and daily chart
screenshots as acceptance references. They are not reverse-engineered into final
rules.

| Case | Owner example | Old spreadsheet conclusion | Available D1 evidence | Current ATHENA output | Missing deterministic evidence |
|---|---|---|---|---|---|
| Strong winner near ATH | JINDWORLD: large D1 breakout to 57.51, RSI 83.60, high volume, price above SuperTrend 42.93. | ATH momentum expansion; hold/ride, do not sell solely on high RSI. | D1 OHLCV and RSI can be computed; ATH/rolling high can be derived; volume spike can be measured; SuperTrend absent. | Valuation, P&L, D1 Trend; Setup only if PS-P9D Sync creates v3 OR evidence. | ATH relationship, blue-sky handling, volume expansion, SuperTrend support, hold/protect guidance. |
| Clean structural uptrend | CHENNPETRO: persistent higher-price structure, price 1452.20 above rising SuperTrend 1274.54, RSI 63.37. | Strong higher-high/higher-low trend; hold full position, protect winner near resistance. | D1 OHLCV, RSI, SMA/EMA, ADX/ATR available; SuperTrend absent. | Likely D1 Trend = UPTREND; no support/target/review prose. | Higher-high/higher-low evidence, SuperTrend support, nearest resistance, review guidance. |
| Breakout | RATNAVEER: strong rally to 304.75, price above SuperTrend 259.88, RSI 74.45. | Breakout / momentum continuation; targets above recent structure. | D1 OHLCV, RSI, ATR/volume available; breakout can be investigated. | D1 Trend only; target columns mostly unavailable. | Breakout lifecycle, failed breakout handling, target derivation. |
| Consolidation near highs | Sheet examples: high-level consolidation near ATH after major momentum expansion. | Hold strong while consolidation holds; add only on clean ATH expansion. | D1 OHLCV can identify tight range after rally if rules are frozen. | No consolidation narrative. | Base/consolidation definition, volatility compression, range boundary extraction. |
| Pullback/reclaim | Sheet examples: Reclaim 610-615, then above 640 breakout; reclaim 510-515 restores trend. | Hold tight; reassess only if reclaim/support fails. | D1 OHLCV supports recent close vs prior levels; RSI/volume can help. | May show UPTREND/MIXED only. | Reclaim level definition, role reversal, returned-above-level lifecycle. |
| Weakening momentum | RAINBOW: price 1447.20 below red SuperTrend 1541.95 after prior rally; RSI 46.59. | Review / hold tight; protect profit, avoid adding below resistance. | D1 OHLCV, RSI available; SuperTrend absent. | Could still show broad SMA trend; no warning about SuperTrend loss. | SuperTrend flip, lower-high/lower-low evidence, resistance overhead, guidance. |
| Damaged structure | Sheet examples with bearish-below or close-below support warnings. | Reassess if structural support fails. | D1 OHLCV can support break-of-support checks. | AT_RISK only if frozen TradePlan/Decision semantics trigger it. | Broken-support evidence and structural damage taxonomy. |
| Downtrend | Any holding below falling structure/SuperTrend. | Avoid adding; only watch reclaim. | D1 OHLCV, SMA, ADX available; SuperTrend absent. | D1 Trend may show DOWNTREND without portfolio review advice. | Lower-high/lower-low, reclaim trigger, review status. |
| Profitable position requiring protection | Sheet rows with +30%-60% P&L and guidance to protect winner. | Hold while support remains intact; protect large profit. | P&L, D1 support candidates, ATR, RSI available. | P&L shown; Next Action may remain HOLD. | Profit-cushion-aware review guidance separate from machine action. |
| Losing position | Negative P&L current holdings such as TARIL/HBLENGINE. | Reassess if support fails; avoid adding until reclaim. | P&L, D1 trend, RSI/ATR/volume available. | May show HOLD/HEALTHY if frozen Decision evidence remains okay. | Separate daily review risk guidance and structural invalidation. |
| Blue-sky / no-overhead resistance | ATH expansion examples such as JINDWORLD/SOLAR-style sheet rows. | Targets may use ATH extension or open-ended target. | ATH/rolling high can be measured from D1 history. | No target extension. | Owner-approved extension methodology; null remains valid until approved. |

## 4. Existing Evidence Inventory

| Evidence | Existing support | PS-P10 usability |
|---|---|---|
| D1 OHLCV | Persisted `Candle` objects, `Timeframe.D1`, repository reads with `as_of`. | Primary source for chart review. |
| Kite/canonical refresh | Existing ingestion/provider abstraction and Portfolio Sync price refresh path. | Use for current holdings only, with canary before expensive runs. |
| SMA/EMA | Indicator engine and calculation primitives exist. | Useful for trend/context, already partly used by PS-P8C. |
| RSI14 | Indicator engine supports RSI. | Directly matches screenshot indicator; needs review-band semantics. |
| ATR | Indicator engine supports ATR. | Required for SuperTrend compatibility and volatility context. |
| MACD | Indicator engine supports MACD. | Candidate momentum context; not required initially unless owner approves. |
| ADX | Indicator engine supports ADX. | Candidate trend-strength context. |
| Volume / Volume MA | Indicator engine supports Volume MA; candles include volume. | Needed for breakout/expansion confirmation. |
| Existing D1 Trend | PS-P8C `PortfolioTrendAdapter` uses SMA20/SMA50 structure. | Keep frozen; may be context for Review only after approval. |
| Existing OR Setup | PS-P9D `PortfolioSetupAdapter` uses M5 OR15/OR30. | Keep frozen and separate; not a D1 chart-review substitute. |
| TradePlan | Decision-owned entry/stop/target evidence. | Do not conflate with chart-review supports/targets. |
| Decision | Canonical advisory Decision artifacts. | Context only; not required for D1 chart review unless approved. |
| Confidence | PS-P7B maps coherent Decision Confidence to Conviction. | Keep frozen; do not replace with numeric chart score. |
| EntryQualification | Intraday actionability evidence. | Keep separate; not a D1 portfolio review input unless a future owner-approved bridge exists. |

## 5. Missing Evidence Inventory

| Missing evidence | Required questions before implementation |
|---|---|
| SuperTrend 10,3 | Exact formula, ATR smoothing, warm-up, initial trend, band carry-forward, flip semantics, point-in-time cutoff. |
| Swing highs/lows | Pivot definition, left/right lookback, confirmation delay, equal highs/lows, stale pivots. |
| Higher-high / higher-low | Number of pivots required, marginal breaks, trend reset after failed breakout. |
| Lower-high / lower-low | Same as above, plus damaged-structure classification. |
| Support/resistance extraction | Pivot source, repeated touches, clustering, zone width, recency, broken level invalidation. |
| Role reversal | When broken resistance becomes support; confirmation by close, touch, retest, or time. |
| ATH / rolling-high relationship | Full-history vs bounded lookback, corporate-action adjusted basis, no-overhead-resistance semantics. |
| Breakout/reclaim | Close vs intraday high, volume requirement, hold duration, false-breakout lifecycle. |
| Consolidation/base | Range tightness, duration, volume compression, position relative to trend/SuperTrend. |
| Volume expansion/compression | Baseline lookback, relative-volume threshold, spike handling, illiquid symbols. |

## 6. SuperTrend Methodology Questions

SuperTrend 10,3 should be treated as strong candidate evidence because it was
visible in the owner's prior daily-chart review workflow. It is not approved as
a decision rule yet.

Required formula/source semantics:

- Inputs: D1 high, low, close; ATR period 10; multiplier 3.
- ATR compatibility: decide whether to reuse ATHENA's existing Wilder ATR
  primitive with period 10 or match TradingView's exact SuperTrend defaults if
  they differ in seeding/rounding.
- Basic bands: candidate formula is median price `(high + low) / 2` plus/minus
  `multiplier * ATR`, but exact carry-forward and flip logic must be frozen.
- Warm-up: define minimum candles. ATR(10) needs at least 11 candles for
  ATHENA's current Wilder ATR primitive; SuperTrend also needs enough prior
  state to stabilize band carry-forward.
- Initial trend: define how the first eligible band/trend is seeded.
- Flip behavior: define close-crossing semantics and whether a same-session
  touch without close can flip.
- Point-in-time: SuperTrend as-of must use only D1 candles with
  `ts_open <= as_of` and must respect completed-candle semantics.
- Replay: deterministic reruns must reproduce the same band, direction, and
  flip point from the same candle sequence.

Explicit non-decisions:

- Above SuperTrend does not automatically mean HOLD STRONG.
- Below SuperTrend does not automatically mean EXIT.
- SuperTrend is evidence until PS-P10C freezes Review consumption.

## 7. Structural-Level Methodology Questions

Support/resistance cannot be "any swing high/low." PS-P10B/PS-P10C must decide:

- Pivot definition: left/right candle count and whether confirmation requires
  future candles, which affects live vs replay behavior.
- Lookback: fixed sessions, volatility-adjusted window, or full visible
  structure.
- Touch count: whether one pivot is enough or repeated touches are required.
- Clustering: how nearby prices become a zone rather than many single levels.
- Zone construction: exact upper/lower boundary, rounding to tick size, and
  whether ATR/percentage widths are allowed.
- Recency: how older levels decay or remain "major."
- Broken support: close-below vs intraday breach, and when the level is removed
  or converted to resistance.
- Role reversal: when old resistance becomes support after a breakout.
- Nearest vs major level: Support 1 should be nearest useful support; Major
  Support / Exit should be the structural invalidation level. They are not
  automatically the same.
- SuperTrend vs structural support: decide precedence when SuperTrend support
  and pivot support disagree.

No new percentage widths or thresholds are approved by PS-P10A.

## 8. ATH / Breakout Methodology Questions

ATH and breakout cases are high-value because the old sheet often used phrases
like "ATH momentum expansion", "fresh breakout", and "blue-sky".

Questions to freeze:

- ATH source: adjusted D1 history, raw Kite candles, or another corporate-action
  aware source.
- Rolling high vs all-time high: whether "ATH" requires all available history
  or a bounded N-session high.
- Breakout confirmation: close above prior high, high above prior high, or close
  plus volume expansion.
- False breakout: how many sessions can return inside the old range before the
  breakout is considered failed.
- Reclaim: whether reclaim means close back above a broken level, or close plus
  sustained hold.
- Consolidation after breakout: how long/tight the post-breakout range must be
  before "healthy consolidation" can be claimed.
- Blue-sky: when there is no overhead resistance, target methodology must be
  separately approved; otherwise target fields remain null or open-ended prose
  remains deferred.

## 9. Target Methodology Questions

Targets need their own methodology. Three target columns do not justify three
invented values.

Candidate sources:

- observed resistance levels above current price;
- recent swing highs;
- prior ATH or rolling high;
- measured move from a confirmed base;
- ATR or volatility extension;
- Fibonacci/percentage extensions, only if owner explicitly approves them.

Required decisions:

- Target 1 vs Target 2 vs Target 3 priority.
- Whether targets must be observed historical levels first.
- Whether an ATH/no-overhead-resistance target may use extension logic.
- Whether targets are levels or zones.
- How to handle targets below current price after a strong move.
- How long targets remain stable before churn is considered excessive.
- Null semantics when no evidence-backed target exists.

Recommendation: PS-P10B should expose candidate target evidence but PS-P10C
should freeze target consumption separately. Do not populate three targets in
PS-P10B.

## 10. Review-Guidance Semantic Proposal

PS-P10 should introduce a separate Portfolio Review / Daily Review layer instead
of silently changing frozen Portfolio Status, Conviction, or Next Action.

Recommended two-layer presentation:

- Machine Action: existing HOLD / WATCH / ADD / EXIT remains frozen and tied to
  current Portfolio/Decision/TradePlan semantics.
- Review Guidance: a deterministic evidence-backed owner-facing sentence, for
  example:
  - "Protect winner; avoid adding below resistance."
  - "Hold while primary support remains intact."
  - "Reassess if structural support fails."
  - "Momentum extended; wait for consolidation or fresh breakout."

Guidance rules must be:

- generated from typed evidence and reason codes;
- deterministic for the same snapshot;
- advisory-only and never order-placement;
- separate from broker execution behavior;
- concise in the table, with detail/provenance available through tooltip or row
  detail.

Do not freeze prose templates in PS-P10A.

## 11. Provenance / Coherency Contract Proposal

Every future chart-review value should carry:

- `evidence_session`: accepted D1 market session date.
- `accepted_price_as_of`: D1 candle timestamp or accepted sync timestamp.
- `analysis_as_of`: snapshot analysis time.
- `methodology_version`: e.g. future `portfolio-review-v0`, not approved here.
- `source_candle_refs`: instrument/timeframe/timestamp range used.
- `indicator_values`: SuperTrend band/direction, RSI14, ATR, volume MA, ADX if
  consumed.
- `structural_levels`: support/resistance/target candidates with source pivot
  timestamps and reason codes.
- `reason_codes`: machine-readable cause for each produced/null field.
- `unavailable_reason`: insufficient history, stale D1, incoherent instrument,
  no level above price, no confirmed pivot, etc.
- `coherency`: instrument id, timeframe, session, and as-of alignment checks.

No screenshot-derived hidden state is allowed.

## 12. Replay Contract

PS-P10B/PS-P10C replay must use persisted D1 candles and should report:

- deterministic reruns over identical candle sequences;
- no future leakage relative to `as_of`;
- historical `as_of` correctness for D1 evidence;
- insufficient-history behavior;
- stale/incoherent evidence handling;
- SuperTrend flips and band stability;
- support/resistance stability;
- level churn and excessive reclassification;
- breakout/reclaim lifecycle behavior;
- target stability;
- representative owner examples from current holdings;
- pathological examples where null is better than weak evidence.

PS-P10A does not invent a pass-rate threshold. Replay should initially report
distributions, transitions, churn, pathological cases, and owner-review samples.

## 13. Explicit Owner Decisions Required

1. Approve PS-P10 as a separate Daily Chart Portfolio Review layer, instead of
   redefining frozen Status/Conviction/Next Action.
2. Decide whether My Portfolio should show a new column/dimension such as
   `Review Guidance`, or reuse the existing 20-column table with detail
   expansion.
3. Decide whether spreadsheet-style statuses (`HOLD STRONG`, `HOLD`,
   `REVIEW / HOLD TIGHT`, `EXIT RISK`) are desired as a new Review Status.
4. Decide whether numeric chart-review conviction is needed, and if yes confirm
   it must be separate from PS-P7B Decision Confidence.
5. Confirm SuperTrend 10,3 as required evidence for PS-P10B, subject to exact
   formula freeze.
6. Decide whether PS-P10B may add a versioned SuperTrend indicator primitive.
7. Decide whether support/resistance levels should be zones or single rounded
   levels.
8. Decide whether Target 1/2/3 may use only observed resistance/swing evidence
   at first.
9. Decide whether ATH/no-overhead-resistance extensions are deferred or included
   in a later methodology review.
10. Decide whether review guidance should be concise table text plus detail
    drawer, or multi-line table prose like the old Google Sheet.

## 14. Recommended PS-P10B Scope

Recommended PS-P10B should implement only reusable evidence primitives, with no
Portfolio Review interpretation yet:

- `SuperTrendEvidence` for D1 SuperTrend 10,3 over persisted candles.
- RSI14 evidence wrapper for Review consumption.
- Volume baseline/expansion evidence over D1 volume and Volume MA.
- Swing high/low candidate extraction.
- Basic structural level candidate object with source candles, but no final
  support/resistance/target consumption.
- ATH/rolling-high relationship evidence.
- Evidence coherency checks: instrument, timeframe, session, as-of, sufficient
  history.
- Tests for owner-style examples, insufficient history, no future leakage,
  SuperTrend flips, and deterministic replay.

Explicitly out of PS-P10B:

- no Portfolio interpreter change;
- no snapshot interpretation-version change;
- no Status/Conviction/Next Action change;
- no support/target population;
- no dashboard behavior change;
- no provider calls from pure evidence code.

## 15. Deferred Concepts

Remain deferred after PS-P10A:

- SuperTrend implementation until PS-P10B authorization.
- Support/resistance methodology freeze until PS-P10C.
- Target 1/2/3 methodology freeze until PS-P10C or later.
- ATH extension formula.
- Numeric chart-review conviction formula.
- Replacement of existing Portfolio Status.
- Replacement of Decision Confidence-based Conviction.
- Replacement of machine Next Action.
- Any coupling from PS-P9D Setup to ADD/EXIT.
- Any use of chart screenshots as production input.
- Historical v0/v1/v2/v3 Portfolio snapshot backfill.
- Any order-placement or execution behavior.

## Validation

- PS-P10A is documentation/discovery only.
- No production Portfolio source change.
- No schema change.
- No API/DTO change.
- No dashboard behavior change.
- No interpretation-version change.
- No indicator implementation.
- No SuperTrend implementation.
- No support/resistance implementation.
- No target implementation.
- `uv.lock` untouched.
