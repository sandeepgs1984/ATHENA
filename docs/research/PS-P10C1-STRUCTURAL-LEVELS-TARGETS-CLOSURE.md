# ATHENA — PS-P10C.1 Structural Levels / Targets Closure

**Status:** Methodology closure complete — ready for Owner / Chief Architect review
**Date:** 2026-09-05
**Scope:** Documentation/replay only. No production Portfolio Review
implementation, schema/API/dashboard change, Portfolio Sync change,
interpretation-version bump, SuperTrend change, or `uv.lock` change.

## 1. Objective

PS-P10C.1 is the final bounded structural-level closure before PS-P10D. Its
purpose is to decide whether ATHENA can safely populate the remaining
Excel-parity fields in `portfolio-daily-review-v0`:

- Support 1;
- Major Support / Invalidation;
- Target 1;
- Target 2;
- Target 3;
- structural Review Trigger;
- `EXIT_RISK`.

This is not a new open-ended research track and does not start PS-P10D.

## 2. Final Decision

**NO-GO.**

Structural zones/targets cannot be made trustworthy enough for v0 without
freezing arbitrary methodology. Keep the following null/deferred in PS-P10D v0:

- Support 1 = null;
- Major Structural Support = null;
- Target 1 = null;
- Target 2 = null;
- Target 3 = null;
- structural Review Trigger = deferred;
- `EXIT_RISK` = deferred.

This closes the structural-level/target topic for v0. Do not create PS-P10C.2.

## 3. Candidate Methodologies Evaluated

Only three bounded alternatives were tested.

### Candidate A — Local Confirmed Swing 2x2

Definition:

- swing low: low is strictly lower than the two prior lows and less-than/equal
  to the two following lows;
- swing high: high is strictly higher than the two prior highs and
  greater-than/equal to the two following highs;
- confirmation delay: 2 D1 candles;
- zone width: pivot candle wick/body zone, not a percentage:
  - support zone = `low` to `min(open, close)`;
  - resistance zone = `max(open, close)` to `high`;
- role reversal: confirmed resistance becomes support only after a later D1
  close above the zone upper boundary;
- broken support: inactive after a D1 close below the zone lower boundary;
- Support 1: nearest active support zone below/around current price;
- Major Support: active support with highest touch count, then recency;
- Targets: nearest active resistance zones above current price, ordered by
  lower boundary.

### Candidate B — ATR/Prominence-Aware 2x2

Definition:

- starts from Candidate A's 2x2 pivot definition;
- requires pivot prominence of at least half the ATR10 difference versus nearby
  highs/lows;
- same zone/lifecycle rules as Candidate A.

This reduced level count but introduced a new half-ATR threshold that is not
owner-frozen.

### Candidate C — Local Confirmed Swing 3x3

Definition:

- same as Candidate A, but with a 3-candle confirmation window on each side;
- confirmation delay: 3 D1 candles;
- same zone/lifecycle rules as Candidate A.

This slightly reduced level count but did not solve churn.

## 4. Replay Method

Replay source: `db/athena.db`

Latest replay cutoff: `2026-09-04T00:00:00+05:30`

Historical replay population:

- 20 current Portfolio holdings;
- 12,095 point-in-time observations after warm-up;
- every pivot exists only after its right-side confirmation candles exist;
- no future candle is allowed to create a level before confirmation;
- all selected current-holding D1 histories are unadjusted.

Representative owner-style symbols:

- CHENNPETRO;
- AZAD;
- JINDWORLD;
- RAINBOW;
- RATNAVEER;
- KSHINTL as strong near available-history high;
- HBLENGINE;
- TARIL;
- TDPOWERSYS;
- WABAG.

## 5. Candidate Replay Metrics

| Candidate | Avg pivot count | Pivot min-max | Observations | Support 1 populated | Major populated | T1 populated | T2 populated | T3 populated | Trigger populated | Any-level churn | Support churn | Target churn |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A: 2x2 local | 179.70 | 27-219 | 12,095 | 11,918 | 11,918 | 11,251 | 10,138 | 9,145 | 11,115 | 10,915 | 10,411 | 4,606 |
| B: 2x2 half-ATR prominence | 21.45 | 2-36 | 12,095 | 10,943 | 10,943 | 7,243 | 4,042 | 2,246 | 9,837 | 5,348 | 4,840 | 1,092 |
| C: 3x3 local | 127.35 | 18-151 | 12,095 | 11,874 | 11,874 | 11,075 | 9,722 | 8,505 | 10,937 | 10,249 | 9,661 | 3,614 |

Interpretation:

- Candidate A produces many levels and high population, but this is false
  confidence: it creates dense duplicate nearby levels and changes frequently.
- Candidate C is not materially better.
- Candidate B reduces clutter, but it does so by introducing a half-ATR
  prominence rule that PS-P10C.1 cannot honestly freeze without more owner
  acceptance. Even then, churn remains high.

## 6. Representative Latest Cases

Candidate A latest levels are shown because it is the simplest non-prominence
baseline.

| Symbol | Current price | Support 1 | Major Structural Support | Resistance 1/2/3 | Review trigger | Useful? |
|---|---:|---|---|---|---|---|
| CHENNPETRO | 1450.00 | 1426.10-1449.00 | 802.30-870.10 | null | 1426.10-1449.00 | Partly useful, but Support 1 sits almost on current price and may be too reactive. |
| AZAD | 2781.00 | 2721.00-2765.10 | 1601.40-1660.00 | 2810.00-2916.90; 2878.00-2942.20; 2899.90-2986.60 | 2549.70-2589.00 | Levels look plausible but targets overlap heavily. |
| JINDWORLD | 57.78 | 53.55-56.00 | 36.38-37.70 | 61.20-61.95; 61.27-62.49; 61.38-63.00 | 43.44-43.96 | Resistance stack is duplicate/overlapping; target ladder would be noisy. |
| RAINBOW | 1445.00 | 1411.20-1518.70 | 1411.20-1518.70 | 1447.90-1469.20; 1475.00-1481.30; 1479.00-1485.20 | 1411.20-1518.70 | Zone is too wide and straddles price; unsuitable as clean Support 1. |
| RATNAVEER | 308.25 | 277.15-291.00 | 150.90-154.00 | null | 272.70-282.98 | Support plausible, but null targets in breakout/blue-sky case. |
| KSHINTL | 1088.00 | 997.65-1059.90 | 847.05-869.00 | null | 997.65-1059.90 | Plausible support; no evidence-backed targets. |
| HBLENGINE | 695.00 | 680.50-693.90 | 453.45-524.05 | 713.00-727.05; 736.50-745.00; 826.00-836.00 | 680.50-693.90 | Useful review areas, but would still not justify EXIT_RISK alone. |
| TARIL | 302.00 | 298.05-305.90 | 279.45-292.80 | 303.00-313.90; 317.05-326.95; 347.30-350.60 | 298.05-305.90 | Too close/overlapping around current price; high false precision risk. |
| TDPOWERSYS | 739.30 | 719.00-733.00 | 409.25-423.50 | 777.30-792.40; 1588.20-1597.70 | 700.40-725.80 | Support plausible, but target ladder jumps from near resistance to stale history. |
| WABAG | 2008.00 | 1985.00-1998.20 | 1346.65-1405.00 | 2161.00-2215.00; 2210.00-2253.50 | 1918.30-1944.00 | Nearby targets overlap; major support is too far to serve daily review cleanly. |

The latest examples prove structural extraction can create useful-looking
levels, but they also expose why freezing it now would be unsafe: duplicates,
overlap, wide zones, stale far-away levels, and support/trigger ambiguity.

## 7. Role Reversal

Role reversal is deterministic under Candidate A:

- confirmed resistance becomes support after a later D1 close above the zone
  upper boundary;
- the new support remains active until a later D1 close below the zone lower
  boundary;
- the pivot does not exist before confirmation.

Replay result:

- role-reversal triggers are common enough to be useful;
- however, when combined with dense local pivots, the nearest role-reversal
  level changes frequently and can overlap with Support 1;
- therefore role reversal is conceptually approved as an important future
  behavior, but not frozen as v0 production methodology.

## 8. Broken Level Lifecycle

The simplest lifecycle tested:

- support breaks on a D1 close below zone lower boundary;
- resistance is consumed/role-reversed on D1 close above zone upper boundary;
- no intraday breach is used;
- no repeated-close confirmation is used;
- no reclaim lifecycle beyond role reversal is frozen.

This is deterministic and point-in-time safe, but still insufficient because the
underlying zones are unstable.

## 9. Targets

Target candidate:

- Target 1 = nearest active confirmed resistance zone above current price;
- Target 2 = next distinct active confirmed resistance zone;
- Target 3 = third distinct active confirmed resistance zone.

Replay problem:

- local swing methods create many nearby overlapping resistance zones;
- target ladders often contain duplicate/near-duplicate levels;
- strong/blue-sky cases legitimately have null targets;
- stale far-away historical highs appear as later targets with weak daily-review
  usefulness.

Final target decision:

- no synthetic extensions;
- no Fibonacci;
- no arbitrary percentage targets;
- no ATR multiples;
- no measured moves;
- keep Target 1/2/3 null in v0.

## 10. EXIT_RISK

`EXIT_RISK` remains deferred.

Reason: PS-P10C.1 did not produce a trustworthy structural invalidation
methodology. Price below SuperTrend or below a noisy local swing zone is not
strong enough to create `EXIT_RISK`.

The approved PS-P10C status taxonomy remains:

- `HOLD_STRONG`;
- `HOLD`;
- `REVIEW_HOLD_TIGHT`;
- null.

## 11. Excel Comparison

The old spreadsheet used visually reviewed levels that were human-filtered for
importance. The tested mechanical candidates do not yet reproduce that judgment
reliably.

| Field | Old Excel behavior | Candidate replay | Final v0 decision |
|---|---|---|---|
| Support 1 | Nearest meaningful support zone | High population, high churn, noisy near-price zones | NO-GO; keep null |
| Major Support / Invalidation | Deeper structural damage zone | Populated often but frequently stale/far from daily-review usefulness | NO-GO; keep null |
| Target 1 | Nearest useful resistance/target | Often populated but duplicates/overlaps/stale | NO-GO; keep null |
| Target 2 | Next useful level | Often duplicate/overlapping | NO-GO; keep null |
| Target 3 | Higher target/extension | Frequently stale or unavailable | NO-GO; keep null |
| Structural Review Trigger | Breakout/reclaim/role-reversal level | Conceptually useful but churns with Support 1 | NO-GO for v0 |
| EXIT_RISK | Human structural invalidation warning | Not trustworthy without stable invalidation | Deferred |

## 12. Final GO / NO-GO

**B. NO-GO.**

Structural zones/targets cannot be made trustworthy without freezing arbitrary
methodology or accepting excessive churn/duplicate levels.

PS-P10D should implement the already approved PS-P10C core only:

- `HOLD_STRONG`;
- `HOLD`;
- `REVIEW_HOLD_TIGHT`;
- null;
- SuperTrend-led chart health;
- RSI/volume context only;
- available-history high context;
- deterministic reason-code guidance;
- position-aware guidance context.

PS-P10D must not populate:

- Support 1;
- Major Structural Support / Invalidation;
- Target 1;
- Target 2;
- Target 3;
- structural Review Trigger;
- `EXIT_RISK`;
- numeric Review Conviction.

## 13. Product Completion Boundary

After Owner/Chief Architect review of PS-P10C.1:

NEXT = PS-P10D implementation.

After PS-P10D:

NEXT = one final Excel-parity / Owner acceptance validation.

Then the Portfolio Daily Review track can close at v0. Any further structural
level sophistication belongs to future backlog, not a blocker.

## 14. Validation

- `git diff --check`: clean.
- No production source changes.
- No Portfolio Sync changes.
- No schema/API/dashboard changes.
- No interpretation-version bump.
- No SuperTrend changes.
- `uv.lock` untouched.

## 15. Proposed Final PS-P10C Documentation Commit

```text
docs(portfolio): close PS-P10C structural level methodology

- Evaluate bounded D1 swing, prominence, role-reversal, support, invalidation,
  and target candidates for PS-P10C.1 without changing production Portfolio
  behavior.
- Record the NO-GO decision for Support 1, Major Structural Support, Target
  1/2/3, structural Review Trigger, and EXIT_RISK in portfolio-daily-review-v0.
- Preserve PS-P10D scope as the approved core Daily Review status/guidance
  methodology only, with structural levels and targets closed for v0.
```
