# ATHENA Portfolio Sync - PS-P8B D1 Trend Methodology Freeze

**Date:** 2026-09-04
**Branch:** `feature/portfolio-sync`
**Milestone:** PS-P8B - methodology/research only
**Status:** Owner / Chief Architect approved and frozen

---

## 1. Executive Summary

PS-P8B narrows PS-P8A's Trend / Setup question into one defensible question:
can ATHENA classify a holding's D1 Trend using only existing approved D1
evidence and without inventing thresholds?

Verdict: approved. ATHENA will classify a holding's D1 Trend by adapting
ATHENA's already-approved Regime SMA20/SMA50 trend rule to the holding's own
D1 candles. The frozen Portfolio Trend taxonomy is:

- `UPTREND`
- `MIXED`
- `DOWNTREND`
- `null` for unavailable or incoherent evidence

`MIXED` has one precise meaning: mixed D1 SMA structure from
the same 20/50 SMA rule, not range, consolidation, or "not uptrend."

Setup remains deferred. PS-P8C is authorized to implement only the D1 Trend
adapter under `portfolio-interpretation-v2`; no Setup implementation, new table,
or historical backfill is authorized.

## 2. Frozen PS-P8A Owner Decisions

Owner / Chief Architect approved and froze PS-P8A on 2026-09-04.

Frozen refinements:

- Trend and Setup are independent dimensions.
- PS-P8B freezes only D1 Trend methodology.
- Setup remains unavailable / deferred.
- D1 Trend is D1-first and D1-owned.
- M5, M15, VWAP, EntryQualification, intraday relative strength, and intraday
  relative volume must not determine D1 Trend.
- DecisionType, TradePlan, stop breach, and Conviction must remain independent
  from Trend.
- PS-P8B is approved/frozen and PS-P8C is authorized to implement only D1 Trend.

## 3. Exact D1 Evidence Inventory

| Evidence | Existing calculation | Existing threshold/config | Semantic meaning today | Timeframe | Persistence / retrieval | Current consumer |
|---|---|---|---|---|---|---|
| D1 close | `Candle.close` | none | price measurement | D1 | `candles`, `list_candles_recent(..., Timeframe.D1, as_of=...)` | indicators, portfolio price |
| SMA | `IndicatorEngine._sma` | `config/indicators.json`: 20 | measurement only | D1 in production scan | persisted indirectly in DecisionReport/run detail, recomputable from candles | scoring technical structure, TradePlan |
| EMA | `IndicatorEngine._ema` | `config/indicators.json`: 21 | measurement only | available generally, not computed in owner-validation scan | recomputable from candles | no current production decision consumer found |
| MACD | `IndicatorEngine._macd` | 12/26/9 | momentum measurement | D1 in production scan | DecisionReport/run detail | scoring technical structure |
| ADX | `IndicatorEngine._adx` | period 14 | trend-strength measurement | D1 in production scan | DecisionReport/run detail | scoring trend bonus |
| RSI | `IndicatorEngine._rsi` | period 14 | momentum measurement | D1 in production scan | DecisionReport/run detail | scoring momentum |
| ATR | `IndicatorEngine._atr` | period 14 | volatility/range measurement | D1 in production scan | DecisionReport/run detail | TradePlan stop/target distance |
| Volume MA | `IndicatorEngine._volume_ma` | period 20 | liquidity measurement | D1 in production scan | DecisionReport/run detail | scoring liquidity |
| Regime trend | `RegimeEngine._trend` | `config/regime.json`: fast 20, slow 50 | market/index trend state | D1 index by default | DecisionReport/run detail | scoring trend, decision direction |
| Scoring trend | `ScoringEngine._trend` | label points + ADX 15/25 + optional confluence bonus | numeric score contribution | mixed D1 market + D1 ADX + intraday confluence | DecisionReport/run detail | composite score |
| Technical structure | `ScoringEngine._technical_structure` | price-vs-SMA points, MACD bonus, VWAP bonus | mixed structure score contribution | D1 SMA/MACD plus optional intraday VWAP | DecisionReport/run detail | composite score |

## 4. Existing Threshold Inventory

| Threshold | Source | Approved current role | Reuse for Portfolio D1 Trend |
|---|---|---|---|
| SMA fast 20 | `config/regime.json` | Regime trend fast SMA | Yes, if adapting Regime trend rule |
| SMA slow 50 | `config/regime.json` | Regime trend slow SMA | Yes, if adapting Regime trend rule |
| Indicator SMA 20 | `config/indicators.json` | D1 indicator / technical structure | Supporting only; same fast period as Regime |
| EMA 21 | `config/indicators.json` | generic EMA measurement | No, no current trend semantic consumer |
| MACD 12/26/9 | `config/indicators.json` | scoring technical bonus | No direct Trend threshold |
| ADX weak 15 / strong 25 | `config/scoring.json` | scoring trend bonus ramp | No direct categorical Trend threshold |
| RSI weak 40 / strong 60 | `config/scoring.json` | momentum score ramp | No direct Trend threshold |
| ATR 14 | `config/indicators.json` | TradePlan/risk distance | No direct Trend threshold |
| VWAP cap 1.5 pct | `config/scoring.json` | intraday technical bonus | Excluded from D1 Trend |

## 5. Existing Semantic Trend Artifacts

ATHENA has one authoritative market/index semantic trend state from
`RegimeEngine._trend`: bull, bear, mixed/third-branch, and unknown labels.

It is not directly usable as a Portfolio holding trend because production
Regime is resolved from configured market index candles. It describes market
regime, not an individual holding's own D1 structure.

No approved typed semantic artifact was found that already means instrument
D1 Trend.

## 6. Scoring Trend Audit

`ScoringEngine._trend` is unsuitable as the owner-facing Trend classifier.

It consumes:

- Regime trend label points (bull 80, mixed 50, bear 20);
- D1 ADX bonus through a 15 -> 25 ramp;
- optional M5/M15 confluence bonus against daily direction.

This is a score contribution, not a categorical trend semantic. It is also
partly market/index based and optionally intraday-dependent, so it violates the
PS-P8B D1-only boundary.

## 7. Technical Structure Audit

`ScoringEngine._technical_structure` is also unsuitable as the direct Trend
classifier.

It consumes:

- D1 close vs D1 SMA(20);
- D1 MACD histogram positive bonus;
- optional same-session VWAP deviation bonus.

It describes structure quality and session positioning as a score contribution.
Because it mixes D1 and intraday evidence when VWAP is present, it cannot be
mapped directly to Portfolio D1 Trend.

## 8. Regime Trend Audit

Regime trend is categorical, D1-based, deterministic, approved, and already
consumed by ScoringEngine and DecisionEngine. Its formula is:

- bull when SMA20 > SMA50 and last close >= SMA50;
- bear when SMA20 < SMA50 and last close <= SMA50;
- mixed otherwise;
- unknown when fewer than 50 candles are available.

Production usage is market/index-level. Therefore it cannot directly populate a
holding row. However, its exact formula can be adapted to an individual
instrument's D1 candles as a new Portfolio D1 Trend methodology because every
threshold and comparison already exists in approved ATHENA methodology.

## 9. D1 / Intraday Boundary

Frozen PS-P8B boundary:

- D1 Trend may use only instrument D1 candles and D1 moving-average comparisons.
- M5, M15, VWAP, EntryQualification, intraday relative strength, and intraday
  relative volume are excluded.
- Missing intraday data must not change D1 Trend.
- Intraday evidence may be used later for Setup/actionability, not Trend.

## 10. Decision / TradePlan Independence

DecisionType must not classify Trend:

- `TRADE` does not imply `UPTREND`.
- `WATCH` does not imply `MIXED`.
- `NO_TRADE` does not imply `DOWNTREND`.

TradePlan is also independent. A holding can have a D1 Trend without an active
TradePlan. Stop breach remains a Portfolio Status/Next Action concern
(`AT_RISK` / `EXIT`), not an automatic Trend downgrade.

## 11. RS / Conviction Independence

Relative Strength must remain separate from absolute technical structure. A
stock can be in `UPTREND` while underperforming its sector.

Conviction from PS-P7B measures confidence in Decision evidence. It must not
gate Trend. Valid combinations may include `UPTREND / LOW` or
`DOWNTREND / HIGH`.

## 12. Setup Deferral

PS-P8B does not freeze:

- `BREAKOUT`
- `PULLBACK`
- `RETEST`
- `CONSOLIDATION`
- `REVERSAL`
- `FAILED_STRUCTURE`

No existing approved ATHENA artifact carries those exact Portfolio Setup
semantics. Recommended classification: `SETUP_METHODOLOGY_DEFERRED`.

## 13. UNKNOWN vs Null Freeze

Do not expose `UNKNOWN` as an owner-facing Trend value in the first production
implementation.

Use:

- `null` = cannot produce a trustworthy classification;
- categorical values = positively classified states.

This matches the frozen Portfolio nullable-field convention and avoids
duplicating `null` with an `UNKNOWN` display value.

## 14. MIXED Freeze

`MIXED` is feasible only under the Regime-derived SMA20/SMA50 mixed-state
meaning. It is positively identified by the existing rule's third branch, not
by "not uptrend" alone.

Approved meaning:

`MIXED` = D1 SMA20/SMA50/close relationship is mixed: neither the bullish
condition nor the bearish condition holds.

It must not mean:

- consolidation;
- range-bound base;
- low volatility;
- support/resistance box;
- no trade;
- weak conviction.

`SIDEWAYS` is not approved as a Portfolio Trend label.

## 15. Candidate Methodologies

| Candidate | Evidence | Thresholds | Null behavior | Advantages | Semantic risks | Replay expectation |
|---|---|---|---|---|---|---|
| A - reuse existing semantic artifact | Current Regime trend | Regime 20/50 SMA rule | `TREND_UNKNOWN` -> null | Already approved, categorical | Market/index, not instrument | Not valid for holdings |
| B - adapt Regime trend formula to instrument D1 | Holding D1 closes, SMA20, SMA50 | Regime fast=20, slow=50 | fewer than 50 D1 candles -> null | D1-only, deterministic, no new thresholds | MIXED label must be narrowly defined | Approved |
| C - keep Trend null | none | none | all rows null | Maximum conservatism | Leaves existing column empty | No behavior change |

## 16. Frozen Methodology

Candidate B is approved:

`UPTREND` when instrument D1 SMA20 > D1 SMA50 and latest D1 close >= D1 SMA50.

`DOWNTREND` when instrument D1 SMA20 < D1 SMA50 and latest D1 close <= D1 SMA50.

`MIXED` when at least 50 D1 candles exist and neither condition holds.

`null` when required D1 evidence is unavailable or incoherent.

This is the only Trend methodology authorized for PS-P8C.

## 17. Exact Evidence Precedence

Frozen precedence:

1. Instrument identity must be canonical and match the Portfolio holding.
2. D1 candle history must be available through the snapshot `as_of`.
3. At least 50 D1 candles must be available.
4. Compute SMA20 and SMA50 over D1 closes only.
5. If SMA20 > SMA50 and close >= SMA50 -> `UPTREND`.
6. Else if SMA20 < SMA50 and close <= SMA50 -> `DOWNTREND`.
7. Else -> `MIXED`.
8. Any incoherency, unavailable evidence, or future evidence -> `null`.

## 18. Reason Codes

Frozen reason-code vocabulary:

- `TREND_UP_FROM_D1_SMA_STRUCTURE`
- `TREND_DOWN_FROM_D1_SMA_STRUCTURE`
- `TREND_MIXED_FROM_D1_SMA_STRUCTURE`
- `TREND_D1_EVIDENCE_UNAVAILABLE`
- `TREND_D1_EVIDENCE_INCOHERENT`
- `SETUP_METHODOLOGY_DEFERRED`

No `UNKNOWN` or `SIDEWAYS` reason code is approved for Portfolio Trend.

## 19. Coherency Contract

Required identity:

- same `instrument_id` as the holding;
- `timeframe = D1`;
- latest trend candle session must equal the accepted Portfolio price session;
- latest trend candle session must equal the expected analysis session when one
  is supplied;
- no previous-session fallback is allowed for Trend classification;
- at least 50 ordered D1 candles;
- SMA calculation uses only candles through the exact accepted session;
- methodology version recorded in row provenance;
- reason codes recorded in row provenance.

Current price must not be combined with stale, prior-session, or future-looking
Trend evidence.

## 20. Replay Dataset

Read-only replay sketch used current real `db/athena.db` persisted data:

- 20 current `portfolio_holdings`;
- D1 candles in `candles`;
- span observed: 2023-08-11 through 2026-09-04;
- latest 30 sessions per current holding for transition sketch;
- latest holding labels joined to latest DecisionType where present.

The sample is intentionally the owner's actual current holdings, not a curated
success set.

## 21. Replay Contract

PS-P8C replay/validation should report:

- deterministic repeat equality for the same input snapshot;
- no future leakage (`ts_open <= as_of`);
- label-transition matrix across consecutive D1 sessions;
- null frequency;
- reason-code distribution;
- examples across `TRADE`, `WATCH`, `NO_TRADE`, no-decision, and each Trend
  label;
- pathological flip-flops for owner inspection;
- explicit proof that missing intraday data does not alter labels;
- no DarvaX or EMR participation.

No pass/fail threshold is invented in PS-P8B.

## 22. Replay Results

Read-only SQL replay of Candidate B over current holdings found:

Latest classification on 2026-09-04:

| Trend | Count |
|---|---:|
| `UPTREND` | 11 |
| `DOWNTREND` | 7 |
| `MIXED` | 2 |
| `null` | 0 |

Latest 30-session transition sketch across current holdings:

| Transition | Count |
|---|---:|
| `UPTREND -> UPTREND` | 323 |
| `DOWNTREND -> DOWNTREND` | 135 |
| `MIXED -> MIXED` | 75 |
| `MIXED -> UPTREND` | 14 |
| `UPTREND -> MIXED` | 13 |
| `MIXED -> DOWNTREND` | 10 |
| `DOWNTREND -> MIXED` | 9 |
| `DOWNTREND -> UPTREND` | 1 |

Full current-holding D1 rows with at least 50 candles: 12,295.
Distribution: 5,728 `UPTREND`, 2,288 `MIXED`, 4,279 `DOWNTREND`.

These are evidence observations, not acceptance thresholds.

## 23. Human Inspection Examples

Latest current-holding examples:

| Instrument | Candidate Trend | Latest Decision | Close | SMA20 | SMA50 |
|---|---|---|---:|---:|---:|
| `NSE:CHENNPETRO` | `UPTREND` | `WATCH` | 1461.50 | 1383.65 | 1245.16 |
| `NSE:KSHINTL` | `UPTREND` | `TRADE` | 1077.05 | 987.37 | 914.18 |
| `NSE:TDPOWERSYS` | `DOWNTREND` | `NO_TRADE` | 737.35 | 1107.30 | 1130.19 |
| `NSE:GESHIP` | `DOWNTREND` | `WATCH` | 1368.80 | 1315.88 | 1369.23 |
| `NSE:RRKABEL` | `MIXED` | `TRADE` | 2452.00 | 2799.95 | 2584.57 |
| `NSE:TEJASNET` | `MIXED` | `WATCH` | 613.75 | 532.33 | 538.38 |

The examples demonstrate Decision independence: `TRADE` appears with both
`UPTREND` and `MIXED`, while `DOWNTREND` appears with `WATCH` and `NO_TRADE`.

## 24. Persistence Recommendation

Recommend Option A: no new persistence table.

If implemented later, derive Trend during Portfolio Sync and store the final
nullable value and reason codes inside immutable Portfolio analysis snapshot
rows, exactly like other Portfolio interpretation outputs.

A reusable ATHENA-wide instrument D1 trend artifact is not required for this
narrow Portfolio field. If later milestones need that artifact outside My
Portfolio, raise it as a separate architecture decision.

## 25. Interpretation Version Recommendation

Do not bump production in PS-P8B.

If PS-P8C implements the first populated Trend value, bump the production
interpreter output to:

`portfolio-interpretation-v2`

Existing `portfolio-interpretation-v0` and `portfolio-interpretation-v1`
snapshots remain immutable and should not be backfilled.

## 26. Known Gaps

- No Setup methodology exists yet.
- No owner-approved range/consolidation definition exists.
- EMA(21) is configured but not part of the live owner-validation indicator set.
- ADX/RSI/MACD support scoring but do not define categorical Trend.
- Replay results are read-only SQL observations, not a committed test harness.
- No owner-reviewed pathological chart pack has been produced yet.

## 27. Owner Decisions Required

| Decision | Frozen owner decision |
|---|---|
| Is trustworthy D1 Trend possible from existing evidence? | Yes, via Candidate B |
| Which candidate is frozen? | Candidate B |
| Is `UPTREND` approved? | Yes, under SMA20 > SMA50 and close >= SMA50 |
| Is `DOWNTREND` approved? | Yes, under SMA20 < SMA50 and close <= SMA50 |
| Is `MIXED` approved? | Yes, only as mixed SMA20/SMA50 D1 structure |
| Is `SIDEWAYS` approved? | No |
| Should missing/unclassified Trend be null rather than `UNKNOWN`? | Yes |
| Evidence precedence? | Use the precedence in section 17 |
| Reason codes? | Section 18 vocabulary approved |
| Is D1-only ownership frozen? | Yes |
| Are intraday/RS/Decision/TradePlan direct classifiers excluded? | Yes |
| Did replay show obvious unacceptable flip-flopping? | No threshold invented; transition matrix looks inspectable and mostly persistent |
| Is more research required before implementation? | No |
| Should implementation use `portfolio-interpretation-v2`? | Yes |
| Should implementation be PS-P8C? | Yes |
| Does Setup remain separate? | Yes |

## 28. Recommended Next Milestone

Authorized next milestone:

**PS-P8C - Portfolio D1 Trend Adapter Implementation**

Scope should be limited to:

- implement the approved D1 Trend adapter;
- pass typed evidence into the pure Portfolio interpreter;
- populate only the Trend dimension in the existing `Trend / Setup` column;
- keep Setup unavailable with `SETUP_METHODOLOGY_DEFERRED`;
- bump interpretation version to `portfolio-interpretation-v2`;
- add deterministic unit, interpreter, sync, currentness, and dashboard tests.

Do not implement Setup in PS-P8C.

## 29. Files Changed

Created:

- `docs/research/PS-P8B-PORTFOLIO-D1-TREND-METHODOLOGY-FREEZE.md`

Modified:

- `docs/MILESTONES.md`
- `IMPLEMENTATION_SUMMARY.md`
- `ATHENA_BRIEFING.md`

No production code changed.

## 30. Suggested Commit Message

```text
docs(portfolio): freeze D1 Trend methodology for review

- Mark PS-P8A owner-approved and frozen per the 2026-09-04 review.
- Freeze PS-P8B Candidate B with UPTREND/DOWNTREND/MIXED/null taxonomy.
- Defer Setup while authorizing PS-P8C to implement D1 Trend only.
```
