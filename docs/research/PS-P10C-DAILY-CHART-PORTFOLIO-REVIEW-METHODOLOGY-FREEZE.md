# ATHENA — PS-P10C Daily Chart Portfolio Review Methodology Freeze

**Status:** Methodology/replay complete — ready for Owner / Chief Architect review
**Date:** 2026-09-05
**Scope:** Methodology and replay only. No production Portfolio Review
population, schema/API/dashboard change, Portfolio Sync wiring, interpretation
version bump, SuperTrend formula change, or numeric Review Conviction.

## 1. Objective

PS-P10C determines whether the PS-P10B evidence foundation can be converted into
useful Daily Chart Portfolio Review intelligence comparable to the owner's
earlier Excel Portfolio Trading Snapshot, without daily chart screenshot
uploads.

The answer is: **PARTIALLY**.

ATHENA can now freeze a useful v0 daily-review layer for chart health and
position-management guidance. ATHENA cannot honestly freeze Excel-style support
zones or Target 1/2/3 ladders yet, because the required pivot/zone/target
methodology would need arbitrary constants that have not earned owner approval.

## 2. Frozen Input Boundary

PS-P10C consumes only approved/coherent evidence:

- `supertrend-10-3-athena-v0`;
- RSI14 raw value;
- D1 volume and Volume MA;
- available-history high relationship;
- optional rolling-high relationship;
- position context: quantity, average price, current P&L percentage;
- existing Portfolio Status/Conviction/Trend/Setup/Next Action only for
  independence comparison, not as required Daily Review inputs.

Production semantics remain untouched:

- existing Portfolio Status remains PS-P5B;
- existing Conviction remains PS-P7B Decision Confidence;
- existing D1 Trend remains PS-P8C SMA20/SMA50;
- existing Setup remains PS-P9D OR15/OR30;
- existing Next Action/ADD/EXIT remain PS-P5B/TradePlan/EntryQualification
  semantics;
- existing TradePlan and EntryQualification remain independent.

## 3. Proposed Methodology Version

Recommended future implementation version:

`portfolio-daily-review-v0`

This is a new Daily Chart Portfolio Review methodology version. It must not
replace `portfolio-interpretation-v3` until a later PS-P10D implementation
milestone explicitly wires it into immutable Portfolio snapshots.

## 4. Review Status Taxonomy

The smallest safe v0 taxonomy is:

- `HOLD_STRONG`
- `HOLD`
- `REVIEW_HOLD_TIGHT`
- `null`

`EXIT_RISK` is **not frozen** in PS-P10C.

Reason: an honest `EXIT_RISK` label requires a frozen structural invalidation
methodology. PS-P10C did not find enough approved evidence to define that
without inventing pivot windows, zone widths, touch counts, or break rules.

Owner-facing display labels may be:

- `HOLD STRONG`
- `HOLD`
- `REVIEW / HOLD TIGHT`
- blank/null

## 5. Review Status Precedence

Proposed deterministic precedence:

1. `EVIDENCE_INCOHERENT` -> null.
2. `EVIDENCE_STALE_OR_SESSION_MISMATCH` -> null.
3. `EVIDENCE_UNAVAILABLE_OR_INSUFFICIENT_HISTORY` -> null.
4. `ST_BULLISH_ABOVE_TRAILING_EVIDENCE` plus
   `LATEST_HIGH_EXCEEDS_PRIOR_AVAILABLE_HISTORY_HIGH` -> `HOLD_STRONG`.
5. `ST_BULLISH_ABOVE_TRAILING_EVIDENCE` -> `HOLD`.
6. `ST_BEARISH_OR_PRICE_BELOW_TRAILING_EVIDENCE` -> `REVIEW_HOLD_TIGHT`.
7. Otherwise -> null.

P&L and average price do not decide Review Status. They may influence guidance
templates only as position-management context.

## 6. Evidence Consumption Rules

### SuperTrend 10,3

SuperTrend is the primary v0 chart-health input:

- bullish direction and close at/above the SuperTrend line supports `HOLD` or
  `HOLD_STRONG`;
- bearish direction or close below the SuperTrend line supports
  `REVIEW_HOLD_TIGHT`;
- fresh flips are exposed as reason context, not automatic ADD/EXIT;
- distance from SuperTrend is descriptive only;
- the SuperTrend line may be shown as trailing structural evidence, but not as
  a guaranteed stop or broker action.

No percentage-distance threshold is introduced.

### RSI14

RSI remains contextual:

- high RSI does not penalize a strong trend;
- low RSI does not create a buy/add signal;
- RSI may add guidance context such as momentum extended, neutral, or weak only
  after owner approves wording templates;
- no RSI threshold is frozen in PS-P10C.

Existing ATHENA scoring has RSI ramp semantics for Scoring, but those are not
Daily Review semantics and are not reused here.

### Volume

Volume remains contextual/descriptive:

- latest volume;
- Volume MA20;
- raw ratio `latest_volume / volume_ma20` when available.

No expansion/compression classification is frozen. Existing intraday RVOL
semantics are not reused because they are session-relative and not D1 portfolio
review methodology.

### Available-History High

Available-history high relationship is allowed for `HOLD_STRONG` only when the
latest D1 high exceeds the prior available-history high on the same raw-history
basis.

This is not an unqualified universal ATH claim. All checked current Portfolio
D1 histories are unadjusted, so corporate-action/source-history limitations
must remain visible.

## 7. Support / Exit Methodology

### Support 1

Recommendation: **defer Support 1**.

PS-P10C does not freeze a Support 1 methodology. Without pivot extraction,
clustering, role reversal, and zone construction, ATHENA cannot honestly produce
the old spreadsheet's support zones.

Support 1 should remain null in PS-P10D v0.

### Major Support / Exit

Recommendation: implement only a conservative `trailing_structure_level` in
Daily Review detail, not the existing Major Support / Exit column, unless the
owner explicitly accepts this narrower semantic.

For bullish SuperTrend evidence:

- `trailing_structure_level = SuperTrend line`.

For bearish SuperTrend evidence:

- `trailing_structure_level = null`;
- review reason explains price is below/under bearish trailing evidence.

This is not a TradePlan stop, not an EXIT action, and not Support 1. If it is
rendered later, label it as trailing structure, not broker stop-loss.

## 8. Zone Construction

Zone construction is **deferred**.

Not frozen:

- pivot confirmation;
- lookback length;
- recency decay;
- clustering width;
- ATR-width zones;
- fixed percentage zones;
- minimum touch count;
- broken-level lifecycle;
- role reversal.

Reason: every candidate requires at least one unfrozen constant or semantic
choice. Forcing a zone methodology now would recreate the old spreadsheet's
usefulness at the cost of ATHENA's determinism and auditability.

## 9. Review Trigger

Do not overwrite existing Key Trigger.

Recommended future field name:

`review_trigger`

Allowed v0 trigger reasons:

- `NEW_AVAILABLE_HISTORY_HIGH` when latest high exceeds prior available-history
  high;
- `BULLISH_ST_RECOVERY` when current session returns to bullish SuperTrend
  state after a prior bearish state;
- `BEARISH_ST_REVIEW` when SuperTrend is bearish or price is below trailing
  evidence.

Resistance/reclaim trigger methodology remains deferred until structural levels
are frozen.

## 10. Target 1 / Target 2 / Target 3

Recommendation: **defer Target 1/2/3 production population**.

Replay showed that a naive "prior available-history high above current close"
target is technically deterministic but not product-safe:

- it is often too far away to be the next useful target;
- it is affected by unadjusted historical highs;
- it does not produce a three-level ladder;
- it does not distinguish nearby resistance from stale ancient highs;
- it churns with source-history/corporate-action basis.

Therefore:

- `Target 1 = null`;
- `Target 2 = null`;
- `Target 3 = null`;

until a structural resistance / target methodology is separately frozen.

## 11. ATH / Blue-Sky Behavior

When no evidence-backed overhead resistance exists, PS-P10D v0 should not invent
synthetic targets.

Forbidden in v0:

- Fibonacci extensions;
- fixed percentage extensions;
- ATR extensions;
- measured moves.

Conservative behavior:

- targets remain null;
- guidance may say price is in available-history breakout / price-discovery
  context when the raw evidence supports it.

This is less rich than the old spreadsheet, but safer and replayable.

## 12. Review Guidance

Guidance should be deterministic reason-code -> template, not free-form LLM
prose.

Proposed v0 reason taxonomy:

- `BULLISH_TRAILING_STRUCTURE_INTACT`
- `NEW_AVAILABLE_HISTORY_HIGH`
- `BEARISH_TRAILING_STRUCTURE_REVIEW`
- `PROFIT_CUSHION_PROTECT_WINNER_CONTEXT`
- `LOSS_CONTEXT_AVOID_ADDING_WITHOUT_RECLAIM`
- `MOMENTUM_EXTENDED_CONTEXT`
- `VOLUME_CONTEXT_ONLY`
- `SUPPORT_METHOD_DEFERRED`
- `TARGET_METHOD_DEFERRED`
- `UNADJUSTED_HISTORY_LIMITATION`

Template principles:

- say what is working;
- name the next observable evidence item;
- distinguish chart state from position context;
- never imply order placement;
- never turn BREAKOUT into ADD or BREAKDOWN into EXIT;
- keep table text concise and move detailed provenance to row detail.

Example template shapes:

- `Hold while SuperTrend trailing structure remains intact; targets deferred.`
- `New available-history high; protect winner, do not treat high RSI alone as a sell signal.`
- `Review closely: price is below bearish SuperTrend evidence; support methodology deferred.`
- `Position is losing money, but loss alone does not create EXIT_RISK; wait for frozen structural invalidation evidence.`

Exact wording should be finalized during PS-P10D UI/API design, after owner
accepts the reason taxonomy.

## 13. Position-Aware Review

Position context is useful, but secondary.

Allowed:

- average price;
- current P&L percentage;
- profit cushion or loss context for guidance wording.

Forbidden:

- large profit alone -> `HOLD_STRONG`;
- loss alone -> `EXIT_RISK`;
- quantity/position size -> status classification;
- average price -> chart-health classification.

Position-aware guidance must preserve the distinction:

- chart state: derived from D1 evidence;
- position-management context: derived from holding economics.

## 14. Numeric Review Conviction

Recommendation: **defer numeric Review Conviction**.

Do not recreate spreadsheet scores such as `9.2`, `8.8`, or `6.9`.

Existing Conviction remains PS-P7B categorical Decision Confidence
`HIGH/MEDIUM/LOW`. No independent numeric daily-review score was found that is
meaningful without introducing arbitrary weights.

## 15. Representative Owner Replay

Replay source: `db/athena.db`

Replay latest session: `2026-09-04`

Current Portfolio holdings checked: 20.

Latest candidate v0 status distribution:

| Candidate status | Count |
|---|---:|
| `HOLD_STRONG` | 1 |
| `HOLD` | 12 |
| `REVIEW_HOLD_TIGHT` | 7 |
| `null` | 0 |

Representative latest cases:

| Symbol | Case | Close | P&L % | ST direction | ST level | RSI14 | Volume / VMA | Candidate review | Notes |
|---|---|---:|---:|---|---:|---:|---:|---|---|
| `JINDWORLD` | strong winner, owner screenshot breakout | 57.78 | +46.95 | BULLISH | 43.01 | 83.72 | 7.60x | HOLD | High RSI and high volume are context only; raw available-history high is 94.25, showing unadjusted-history limitation. |
| `CHENNPETRO` | clean uptrend | 1450.00 | +68.50 | BULLISH | 1276.81 | 64.52 | 0.37x | HOLD | Strong chart/position context, but no new available-history high. |
| `RATNAVEER` | breakout / momentum | 308.25 | data not in current holdings | BULLISH | 255.59 | not in holdings replay | not in holdings replay | reference only | PS-P10B.1 confirmed screenshot direction agreement; not a current holding row. |
| `KSHINTL` | available-history high | 1088.00 | +34.73 | BULLISH | 934.08 | 73.75 | 1.15x | HOLD_STRONG | Only current holding where raw latest high exceeded prior available-history high. |
| `RAINBOW` | weakening momentum / bearish ST | 1445.00 | +12.33 | BEARISH | 1541.77 | 46.25 | 0.56x | REVIEW_HOLD_TIGHT | Matches owner screenshot direction: review/protect, not automatic exit. |
| `HBLENGINE` | damaged / losing position | 695.00 | -13.32 | BEARISH | 714.13 | 50.76 | 9.03x | REVIEW_HOLD_TIGHT | Loss and high volume are context; no EXIT_RISK without structural invalidation. |
| `TARIL` | damaged / losing position | 302.00 | -21.53 | BEARISH | 313.80 | 48.74 | 0.40x | REVIEW_HOLD_TIGHT | Loss alone does not create EXIT_RISK. |
| `TDPOWERSYS` | profit but bearish ST | 739.30 | +27.14 | BEARISH | 957.67 | 30.86 | 0.63x | REVIEW_HOLD_TIGHT | Protect/review context despite positive P&L; no automatic sell. |

Full 20-holding latest replay:

| Symbol | Candidate status | Reason | Close | ST | RSI14 | Volume / VMA | Target safe? |
|---|---|---|---:|---:|---:|---:|---|
| BALKRISIND | HOLD | BULLISH_ST_ABOVE_TRAILING_EVIDENCE | 2285.00 | 2232.09 | 43.47 | 0.43x | No |
| CHENNPETRO | HOLD | BULLISH_ST_ABOVE_TRAILING_EVIDENCE | 1450.00 | 1276.81 | 64.52 | 0.37x | No |
| GESHIP | REVIEW_HOLD_TIGHT | BEARISH_ST_REVIEW_REQUIRED | 1366.20 | 1423.35 | 54.69 | 1.14x | No |
| GRANULES | REVIEW_HOLD_TIGHT | BEARISH_ST_REVIEW_REQUIRED | 849.80 | 892.77 | 52.01 | 1.77x | No |
| HBLENGINE | REVIEW_HOLD_TIGHT | BEARISH_ST_REVIEW_REQUIRED | 695.00 | 714.13 | 50.76 | 9.03x | No |
| HINDCOPPER | HOLD | BULLISH_ST_ABOVE_TRAILING_EVIDENCE | 521.55 | 508.59 | 46.72 | 0.23x | No |
| JINDRILL | HOLD | BULLISH_ST_ABOVE_TRAILING_EVIDENCE | 663.95 | 584.54 | 63.79 | 0.53x | No |
| JINDWORLD | HOLD | BULLISH_ST_ABOVE_TRAILING_EVIDENCE | 57.78 | 43.01 | 83.72 | 7.60x | No |
| KSHINTL | HOLD_STRONG | BULLISH_ST_NEW_AVAILABLE_HISTORY_HIGH | 1088.00 | 934.08 | 73.75 | 1.15x | No |
| MAZDOCK | HOLD | BULLISH_ST_ABOVE_TRAILING_EVIDENCE | 2484.00 | 2425.24 | 47.44 | 0.97x | No |
| MUFIN | HOLD | BULLISH_ST_ABOVE_TRAILING_EVIDENCE | 136.87 | 128.34 | 55.56 | 1.12x | No |
| NEPHROPLUS | HOLD | BULLISH_ST_ABOVE_TRAILING_EVIDENCE | 700.00 | 630.15 | 54.94 | 1.03x | No |
| RAINBOW | REVIEW_HOLD_TIGHT | BEARISH_ST_REVIEW_REQUIRED | 1445.00 | 1541.77 | 46.25 | 0.56x | No |
| RRKABEL | REVIEW_HOLD_TIGHT | BEARISH_ST_REVIEW_REQUIRED | 2459.00 | 2876.93 | 34.21 | 4.64x | No |
| TARIL | REVIEW_HOLD_TIGHT | BEARISH_ST_REVIEW_REQUIRED | 302.00 | 313.80 | 48.74 | 0.40x | No |
| TDPOWERSYS | REVIEW_HOLD_TIGHT | BEARISH_ST_REVIEW_REQUIRED | 739.30 | 957.67 | 30.86 | 0.63x | No |
| TEJASNET | HOLD | BULLISH_ST_ABOVE_TRAILING_EVIDENCE | 612.00 | 518.21 | 71.52 | 5.12x | No |
| TIMEX | HOLD | BULLISH_ST_ABOVE_TRAILING_EVIDENCE | 670.00 | 582.13 | 67.99 | 0.91x | No |
| WABAG | HOLD | BULLISH_ST_ABOVE_TRAILING_EVIDENCE | 2008.00 | 1918.20 | 50.35 | 0.30x | No |
| WELSPUNLIV | HOLD | BULLISH_ST_ABOVE_TRAILING_EVIDENCE | 209.50 | 182.89 | 80.33 | 0.67x | No |

## 16. Historical Replay Safety

Historical replay across current holdings:

- holdings: 20;
- point-in-time observations: 12,295;
- deterministic candidate status states observed: 3;
- Support 1 safe population: 0/12,295;
- naive available-history-high target above close: 12,018/12,295, but rejected
  as unsafe target methodology;
- no-overhead available-history-high cases: 277/12,295;
- available-history high flag transitions: 571.

Historical candidate status distribution:

| Status | Observations |
|---|---:|
| `HOLD` | 6,198 |
| `REVIEW_HOLD_TIGHT` | 5,533 |
| `HOLD_STRONG` | 564 |
| `null` | 0 |

Historical status transitions:

| Transition | Count |
|---|---:|
| `HOLD -> HOLD_STRONG` | 269 |
| `HOLD_STRONG -> HOLD` | 283 |
| `HOLD -> REVIEW_HOLD_TIGHT` | 152 |
| `REVIEW_HOLD_TIGHT -> HOLD` | 141 |
| `REVIEW_HOLD_TIGHT -> HOLD_STRONG` | 13 |

Highest status churn examples:

| Symbol | Transitions | PIT observations | Distribution |
|---|---:|---:|---|
| TDPOWERSYS | 93 | 710 | 205 REVIEW, 440 HOLD, 65 HOLD_STRONG |
| WABAG | 84 | 710 | 234 REVIEW, 412 HOLD, 64 HOLD_STRONG |
| GRANULES | 74 | 710 | 332 REVIEW, 321 HOLD, 57 HOLD_STRONG |
| HBLENGINE | 65 | 710 | 314 REVIEW, 351 HOLD, 45 HOLD_STRONG |
| CHENNPETRO | 54 | 710 | 317 REVIEW, 366 HOLD, 27 HOLD_STRONG |
| MAZDOCK | 52 | 710 | 370 REVIEW, 315 HOLD, 25 HOLD_STRONG |

Replay conclusion:

- Status v0 is deterministic and useful.
- Support and target fields should remain null until methodology is stronger.
- Naive target availability is misleadingly high and would be product-dangerous.
- Available-history high behavior churns enough that it should support
  `HOLD_STRONG` only on the latest raw evidence, not synthetic targets.

## 17. Excel-Parity Acceptance Matrix

| Excel field | Old human/chart methodology | Current ATHENA value | Proposed PS-P10 methodology | Evidence source | Deterministic? | Replay result | Safe to implement? | Still deferred? |
|---|---|---|---|---|---|---|---|---|
| Status | Chart health / hold-review label | Existing Portfolio Status | New separate Daily Review Status: HOLD_STRONG/HOLD/REVIEW_HOLD_TIGHT/null | SuperTrend + available-history high | Yes | 3 states over 12,295 observations | Yes, after owner approval | EXIT_RISK deferred |
| Conviction | Numeric chart score | PS-P7B HIGH/MEDIUM/LOW | No numeric review score | None | n/a | No defensible score | No | Yes |
| Trend / Setup | Rich chart prose | PS-P8C Trend + PS-P9D Setup | Keep unchanged; Daily Review separate | Existing frozen adapters | Yes | Independence preserved | No change | Daily narrative separate |
| Key Trigger | Breakout/reclaim levels | TradePlan entry trigger only | Do not overwrite; add future `review_trigger` | ST flip/high relationship | Partially | New high trigger available; reclaim deferred | Partial | Reclaim/resistance trigger deferred |
| Support 1 | Nearest support zone | null/deferred | Keep null in v0 | Structural candidates not frozen | No | 0 safe observations | No | Yes |
| Major Support / Exit | Structural invalidation / ST / stop region | TradePlan stop when coherent | Do not overwrite; optional trailing-structure detail = ST line | SuperTrend | Yes | Available for bullish rows | Partial | True exit/invalidation deferred |
| Target 1 | Nearest resistance/extension | TradePlan target if coherent | Keep null in v0 | Available-history high rejected as unsafe target | Partially | 12,018 naive candidates rejected | No | Yes |
| Target 2 | Higher resistance/extension | null/deferred | Keep null | none frozen | No | n/a | No | Yes |
| Target 3 | Higher/blue-sky extension | null/deferred | Keep null | none frozen | No | n/a | No | Yes |
| Next Action | Prose management action | Frozen HOLD/WATCH/ADD/EXIT | Keep unchanged; add Review Guidance separately | Reason templates | Yes | Template taxonomy viable | Partial | Exact UI/API wording deferred |
| Review Guidance | Human chart note | Not present | Deterministic reason-code templates | Status + ST + position context | Yes | Viable with null support/target caveats | Yes, after owner approval | Final wording deferred |

## 18. Product Acceptance Answer

If PS-P10D implements only the methodology recommended here, My Portfolio will
**PARTIALLY** replace the previous Excel + daily chart screenshot workflow.

It will replace:

- daily chart health status;
- SuperTrend-based review context;
- ATH/available-history breakout context;
- RSI and volume measurement context;
- position-aware guidance boundaries;
- deterministic review reasons.

It will not yet replace:

- Support 1 zones;
- Major Support / Exit structural invalidation zones;
- Target 1/2/3 ladders;
- reclaim/resistance triggers;
- numeric Review Conviction;
- rich multi-line handwritten chart prose.

This is the correct boundary for a trustworthy v0. Filling the missing columns
requires PS-P10D/PS-P10E-style implementation only after the owner accepts the
deferred methodology choices.

## 19. Required Owner Decisions

1. **Review Status taxonomy:** approve `HOLD_STRONG`, `HOLD`,
   `REVIEW_HOLD_TIGHT`, `null`; keep `EXIT_RISK` deferred.
2. **Review Status precedence:** approve evidence/null precedence in §5.
3. **SuperTrend consumption:** approve SuperTrend as primary v0 chart-health
   input; distance/fresh flip descriptive only.
4. **RSI consumption:** approve context-only RSI14; no overbought/oversold
   status thresholds.
5. **Volume consumption:** approve raw volume/VMA context only; no expansion
   multiplier.
6. **Support 1 methodology:** defer; keep Support 1 null in PS-P10D v0.
7. **Major Support / Exit methodology:** do not overwrite existing field; decide
   whether `trailing_structure_level = ST line` belongs in a new detail field.
8. **Zone construction:** defer pivot/zone methodology.
9. **Review Trigger semantics:** keep existing Key Trigger frozen; approve a
   separate future `review_trigger`.
10. **Target 1/2/3 methodology:** defer; keep target columns null in v0.
11. **ATH/no-resistance behavior:** no synthetic targets; guidance only.
12. **Review Guidance reason taxonomy:** approve §12 reason-code set as v0
    starting point.
13. **Position-aware guidance:** allow P&L/Avg Price in guidance context only,
    never status classification.
14. **Numeric Review Conviction:** defer.
15. **Null/unavailable precedence:** approve incoherent/stale/unavailable ->
    null before classification.
16. **Methodology version:** approve `portfolio-daily-review-v0`.
17. **PS-P10D scope:** implement evidence-to-review DTO/snapshot population only
    for approved v0 status, reasons, review guidance, and optional trailing
    structure detail; no support zones, target ladders, numeric conviction, or
    dashboard redesign unless separately authorized.

## 20. Validation

- `git diff --check`: clean.
- Production Portfolio source unchanged.
- Portfolio Sync unchanged.
- PortfolioInterpreter unchanged.
- Schema unchanged.
- API/DTO unchanged.
- Dashboard behavior unchanged.
- OpeningRangeEngine unchanged.
- PortfolioTrendAdapter unchanged.
- PortfolioSetupAdapter unchanged.
- `supertrend-10-3-athena-v0` unchanged.
- Portfolio interpretation version unchanged.
- `uv.lock` untouched.

## 21. Proposed Documentation Commit

```text
docs(portfolio): freeze PS-P10C daily review methodology

- Define the conservative portfolio-daily-review-v0 methodology for Daily Chart
  Portfolio Review status, reason codes, SuperTrend consumption, and guidance
  boundaries without changing production Portfolio behavior.
- Replay the candidate methodology across current holdings and historical
  point-in-time D1 evidence, documenting status distributions, churn, target
  rejection, support deferral, and unadjusted-history limitations.
- Record the Excel-parity matrix and required Owner decisions before any PS-P10D
  implementation.
```
