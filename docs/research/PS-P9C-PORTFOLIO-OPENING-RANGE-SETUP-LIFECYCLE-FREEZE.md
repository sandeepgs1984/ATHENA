# ATHENA Portfolio Sync - PS-P9C Opening-Range Setup Lifecycle Freeze

**Date:** 2026-09-05
**Branch:** `feature/portfolio-sync`
**Milestone:** PS-P9C - methodology/research only
**Status:** Owner / Chief Architect approved and frozen 2026-09-05

---

## 1. Executive Summary

PS-P9C evaluated whether the approved Opening Range evidence can support the
smallest deterministic structural Portfolio Setup methodology after resolving
directionality, OR15/OR30 precedence, returned-inside behavior, intraday
lifecycle, and post-close lifecycle.

Verdict: Candidate L1 is frozen for PS-P9D implementation.

L1 is conservative: it emits `BREAKOUT` only when OR15 and OR30 both show active
upside breakout with no returned-inside behavior, emits `BREAKDOWN` only when
both show active downside breakdown with no returned-inside behavior, and
otherwise emits null with provenance. Replay shows L1 suppresses many one-window
or returned-inside cases, but the remaining labels are directional,
deterministic, explainable, and free of direct `BREAKOUT -> BREAKDOWN` flips in
the checkpoint grid.

Production remained unchanged during PS-P9C: Setup was still null and Portfolio
interpretation remained `portfolio-interpretation-v2`.

## 2. Frozen PS-P9B Decisions

PS-P9B is Owner / Chief Architect approved and frozen 2026-09-04.

Frozen findings:

- Setup is structural first, not actionable.
- Opening Range evidence is the strongest current core Setup candidate.
- Direction must be preserved.
- Upside structure may eventually map to `BREAKOUT`.
- Downside structure may eventually map to `BREAKDOWN`.
- `BREAKDOWN` must never imply `EXIT`, `AT_RISK`, or `DOWNTREND`.
- EntryQualification, VWAP, intraday trend, RS, RVOL, D1 Trend, DecisionType,
  Conviction, and Key Trigger remain independent context only.
- DarvaX and EMR remain excluded.
- Missing/stale/incoherent evidence produces owner-facing null with provenance.
- Future populated Setup should use `portfolio-interpretation-v3`.

## 3. Candidate Taxonomy

Evaluate only:

- `BREAKOUT`
- `BREAKDOWN`
- null

Do not add `PULLBACK`, `RETEST`, `CONSOLIDATION`, `BASE`, `REVERSAL`,
`FAILED_BREAKOUT`, or `FAILED_STRUCTURE`.

## 4. Structural Setup Semantic

Setup describes the current Opening Range structure evidenced for the accepted
session. It does not state whether to trade. It must not require
`DecisionType=TRADE`, `EntryQualification=QUALIFIED`, HIGH Conviction, or D1
`UPTREND`.

## 5. OR15 Contract

OR15 is the first 15 minutes of the regular session, sourced from
`SessionContext.session_open_ts`, completed canonical M5 candles, and the real
`OpeningRangeEngine`. It is usable only when formation status is `COMPLETE`.

Replay reused PS-P9B's same population: OR15 was `COMPLETE` in 32,853 / 35,232
observations.

## 6. OR30 Contract

OR30 is the first 30 minutes of the regular session, also completed-canonical-M5
only and independently represented. It is not canonically superior in upstream
methodology.

Replay: OR30 was `COMPLETE` in 24,147 / 35,232 observations, with 5,304
`FORMING` and 5,781 `INCOMPLETE_DATA` observations. This availability gap is
the main usability cost of L1.

## 7. Candidate L1

Frozen rule:

- OR15 event and OR30 event both `UPSIDE_BREAKOUT_EVENT`, and neither required
  window returned inside range -> `BREAKOUT`.
- OR15 event and OR30 event both `DOWNSIDE_BREAKDOWN_EVENT`, and neither
  required window returned inside range -> `BREAKDOWN`.
- Opposite directions -> null / `SETUP_OR_WINDOWS_CONFLICT`.
- Returned-inside in either required window -> null /
  `SETUP_RETURNED_INSIDE_RANGE`.
- Required OR window incomplete/forming/unavailable -> null /
  `SETUP_OR_INCOMPLETE`.
- No valid OR event -> null / `SETUP_NOT_PRESENT`.
- One-window-only event -> null / `SETUP_SINGLE_WINDOW_ONLY`.

PS-P9C final owner refinement freezes deterministic null-reason precedence from
highest to lowest:

1. `SETUP_EVIDENCE_INCOHERENT`
2. `SETUP_EVIDENCE_STALE`
3. `SETUP_EVIDENCE_UNAVAILABLE`
4. `SETUP_OR_INCOMPLETE`
5. `SETUP_OR_WINDOWS_CONFLICT`
6. `SETUP_RETURNED_INSIDE_RANGE`
7. `SETUP_SINGLE_WINDOW_ONLY`
8. `SETUP_NOT_PRESENT`

Overlap examples:

- OR15 downside and returned-inside, OR30 upside and not returned-inside ->
  null / `SETUP_OR_WINDOWS_CONFLICT`, because conflict outranks
  returned-inside.
- OR15 complete active event and OR30 forming/incomplete -> null /
  `SETUP_OR_INCOMPLETE`, not `SETUP_SINGLE_WINDOW_ONLY`.
- Both windows complete with exactly one active event -> null /
  `SETUP_SINGLE_WINDOW_ONLY`.
- Both windows complete with no active event -> null / `SETUP_NOT_PRESENT`.

Lifecycle:

- Intraday Setup is a stateless point-in-time classification from current
  accepted evidence.
- Setup may appear, disappear, or reappear intraday as OR evidence evolves.
- Conflict and returned-inside produce null; later same-direction agreement can
  re-establish Setup.
- No consumed-state memory is introduced.
- Post-close, retain the final accepted session Setup as the latest completed
  session structural snapshot.
- Weekend/holiday views may retain the latest completed trading session Setup
  with source-session provenance.
- The next trading session hard-resets Setup.

Context independence:

- Setup does not consume EQ, VWAP, intraday trend, RS, RVOL, DecisionType,
  Conviction, D1 Trend, TradePlan, Key Trigger, Status, Action, or P&L.
- `BREAKDOWN` does not mean `EXIT`, `AT_RISK`, or `DOWNTREND`.
- No thresholds are introduced.

## 8. Candidate L2

L2 permits OR15-first labels before OR30 confirms:

- completed OR15 active upside/downside event -> `BREAKOUT`/`BREAKDOWN`;
- OR15 returned-inside -> null;
- once OR30 is complete, opposite OR30 direction or returned-inside nulls the
  label.

L2 improves label count but adds lifecycle complexity and premature early
session labeling.

## 9. Candidate L3

Continue deferral: production Setup remains null.

L3 is still safe, but PS-P9C evidence shows L1 is conservative enough to freeze
for owner review if the owner accepts suppression of OR15-only events.

## 10. OR15-Only Analysis

L1 suppressed 2,213 OR15-only observations. This is expected: L1 intentionally
waits for OR30 agreement rather than creating a provisional label.

Recommendation: OR15-only Setup should not be owner-facing in v3. It may remain
provenance/context if PS-P9D is implemented.

## 11. OR30-Only Analysis

Replay found zero cases where OR15 had no/not-observed event and OR30 alone
produced upside or downside. In this dataset, OR30 did not independently create
new direction without OR15 already having an event.

Recommendation: OR30-only Setup should not be a separate production path.

## 12. Agreement Analysis

Raw agreement observations:

- OR15 upside + OR30 upside: 3,541.
- OR15 downside + OR30 downside: 5,854.
- Same-direction agreement suppressed by returned-inside behavior: 6,660.

Active L1 labels after returned-inside nulling:

- `BREAKOUT`: 1,019.
- `BREAKDOWN`: 1,716.

Recommendation: same-direction active agreement is the only Setup-producing
condition for the first implementation.

## 13. Conflict Analysis

L1 found 524 opposite-direction OR15/OR30 conflicts. Conflict must render null
with `SETUP_OR_WINDOWS_CONFLICT`; choosing OR15 or OR30 precedence would be
arbitrary and is not supported by existing methodology.

## 14. Returned-Inside Analysis

Returned-inside is represented independently per OR window. L1 uses:

`any required window returned_inside == true -> null`.

Replay: 9,065 L1 observations null due to returned-inside. This is load-bearing
and prevents stale historical breakout/breakdown events from masquerading as
current active structure.

## 15. Direction-Reversal Analysis

L1 produced zero same-session groups containing both `BREAKOUT` and `BREAKDOWN`
and zero direct `BREAKOUT -> BREAKDOWN` or `BREAKDOWN -> BREAKOUT` transitions
across consecutive checkpoints.

L2 also produced zero direct flips in this checkpoint grid, but does so with
more early-session labels and more returned-inside churn.

## 16. Point-in-Time Lifecycle

Recommended lifecycle:

- Setup is evaluated at Portfolio analysis timestamp.
- It may change intraday.
- It has no consumed state.
- Returned-inside removes the active Setup label.
- Conflict removes the active Setup label.
- Later same-direction active agreement can re-establish a Setup if the OR
  evidence itself supports it.

## 17. Pre-Open / Formation Behavior

Pre-open and required-window formation produce null. Do not show partial-range
or predicted Setup. Under L1, OR30 must be complete before any owner-facing
Setup label is possible.

## 18. Post-Close Behavior

Recommend Model A: after close, display the final accepted session Setup as a
latest-session structural snapshot, not as current actionability.

This is consistent with the structural-first semantic and preserves replayable
end-of-day Portfolio Sync.

## 19. Weekend/Holiday Behavior

If PS-P9D implements Setup, weekend/holiday display may retain the latest
completed trading session's final Setup with source session/as-of provenance.
It must not imply a live current-session signal.

## 20. Next-Session Reset

Opening Range Setup is session-owned. A prior session's Setup must not carry
into a new session. At the next session open, Setup resets to null until the
required current-session OR evidence completes and agrees.

## 21. Freshness/Coherency Contract

Future implementation should persist/provenance:

- instrument id;
- market session date;
- analysis `as_of`;
- OR15 evidence `as_of`;
- OR30 evidence `as_of`;
- latest completed canonical M5 slot;
- no future M5 evidence;
- methodology version;
- setup label;
- reason/null reason;
- OR window statuses, events, relations, first event timestamps, and
  returned-inside flags.

## 22. Replay Dataset

Read-only replay used `db/athena.db`, SQLite URI `mode=ro`, the real
`OpeningRangeEngine`, persisted M5 candles, latest per-instrument Decisions,
and the same session/checkpoint population as PS-P9B.

Dataset:

- 2026-08-14 through 2026-09-04;
- checkpoints: 09:30, 09:45, 10:00, 11:00, 13:00, 14:30 IST;
- 35,232 observations;
- 398 instruments;
- 6,065 instrument-session groups.

This is a market-time replay over data currently persisted in ATHENA, not a
knowledge-time/bitemporal reconstruction.

## 23. Candidate Replay Results

L1:

- `BREAKOUT`: 1,019.
- `BREAKDOWN`: 1,716.
- null: 32,497.

L2:

- `BREAKOUT`: 2,152.
- `BREAKDOWN`: 3,551.
- null: 29,529.

L2 emits roughly twice as many active labels, but by accepting OR15-first
semantics before OR30 agreement. PS-P9C recommends L1 because it is simpler and
more conservative.

## 24. Transition Matrix

L1 top consecutive-checkpoint transitions:

- `null -> null`: 25,741.
- `BREAKDOWN -> BREAKDOWN`: 862.
- `null -> BREAKDOWN`: 830.
- `null -> BREAKOUT`: 515.
- `BREAKOUT -> BREAKOUT`: 484.
- `BREAKDOWN -> null`: 430.
- `BREAKOUT -> null`: 305.
- `BREAKOUT -> BREAKDOWN`: 0.
- `BREAKDOWN -> BREAKOUT`: 0.

L2 top transitions:

- `null -> null`: 22,242.
- `BREAKDOWN -> BREAKDOWN`: 2,115.
- `null -> BREAKDOWN`: 1,350.
- `BREAKOUT -> BREAKOUT`: 1,198.
- `null -> BREAKOUT`: 864.
- `BREAKDOWN -> null`: 784.
- `BREAKOUT -> null`: 614.
- direct opposite-direction flips: 0.

## 25. Final-Session Distribution

L1 final checkpoint state by instrument-session:

- `BREAKOUT`: 230.
- `BREAKDOWN`: 424.
- null: 5,411.

Final null reasons:

- `SETUP_RETURNED_INSIDE_RANGE`: 2,863.
- `SETUP_OR_INCOMPLETE`: 1,157.
- `SETUP_NOT_PRESENT`: 982.
- `SETUP_OR_WINDOWS_CONFLICT`: 222.
- `SETUP_SINGLE_WINDOW_ONLY`: 187.

## 26. Null-Reason Distribution

L1 null reasons across all observations:

- `SETUP_OR_INCOMPLETE`: 11,085.
- `SETUP_NOT_PRESENT`: 9,610.
- `SETUP_RETURNED_INSIDE_RANGE`: 9,065.
- `SETUP_SINGLE_WINDOW_ONLY`: 2,213.
- `SETUP_OR_WINDOWS_CONFLICT`: 524.

This taxonomy cleanly distinguishes no setup from missing/incomplete evidence.

## 27. Future-Leakage Validation

The replay reran every observation with later same-day M5 candles supplied while
holding `as_of` fixed. OR evidence and L1/L2 classifications were unchanged.

Future-leakage defects: 0.

## 28. Human Review Cases

Representative cases:

| Case | Symbol/session/checkpoint | L1 result | Finding |
|---|---|---|---|
| Clean upside agreement | `NSE:BERGEPAINT`, 2026-08-14 10:00 | `BREAKOUT` | OR15 and OR30 upside, returned-inside false. |
| Clean downside agreement | `NSE:AARTIIND`, 2026-08-14 10:00 | `BREAKDOWN` | OR15 and OR30 downside, returned-inside false. |
| OR15 event while OR30 forming | replayed in L2 population | L1 null | L1 intentionally waits for OR30. |
| OR15/OR30 conflict | `NSE:IIFL`, 2026-08-14 11:00 | null/conflict | OR15 downside-returned, OR30 upside. |
| Breakout returned inside | `NSE:ADANIPORTS`, 2026-08-14 09:45 | null/returned-inside | Prior upside event no longer active. |
| Breakdown returned inside | `NSE:AIIL`, 2026-08-14 09:45 | null/returned-inside | Prior downside event no longer active. |
| Direction reversal | no L1 direct reversal found | none | L1 avoided opposite active flips. |
| No-event session | `NSE:360ONE`, 2026-08-14 09:45 | null/not-present | Complete evidence without active setup. |
| Post-close final setup | `NSE:360ONE`, 2026-08-14 14:30 | `BREAKDOWN` | Latest-session structural snapshot candidate. |
| Next-session reset | `NSE:360ONE`, 2026-08-14 final -> 2026-08-17 09:30 | null/incomplete | Prior session setup does not carry forward. |

D1 Trend, Decision, and EQ were retained as context only in examples.

## 29. Candidate Comparison

L1 is the recommended methodology:

- conservative;
- directional;
- deterministic;
- threshold-free;
- no invented confirmation indicators;
- no direct opposite-direction flips in replay;
- clear null provenance.

L2 is not recommended for first implementation because it introduces
early-session OR15-first semantics and a quasi-provisional lifecycle without a
need strong enough to justify that complexity.

L3 remains safe but is not preferred after PS-P9C replay.

## 30. Recommended Methodology or Deferral

Outcome A: L1 is frozen as the minimal Portfolio Opening Range Setup
methodology.

PS-P9D implementation is authorized only after this PS-P9C freeze.

## 31. Reason-Code Recommendation

Freeze these conceptual reasons for PS-P9D naming/finalization:

- `SETUP_BREAKOUT_FROM_OPENING_RANGE_AGREEMENT`
- `SETUP_BREAKDOWN_FROM_OPENING_RANGE_AGREEMENT`
- `SETUP_NOT_PRESENT`
- `SETUP_OR_INCOMPLETE`
- `SETUP_OR_WINDOWS_CONFLICT`
- `SETUP_RETURNED_INSIDE_RANGE`
- `SETUP_EVIDENCE_UNAVAILABLE`
- `SETUP_EVIDENCE_STALE`
- `SETUP_EVIDENCE_INCOHERENT`
- `SETUP_SINGLE_WINDOW_ONLY`

Owner-facing Setup labels remain only `BREAKOUT`, `BREAKDOWN`, and `-`.

## 32. Interpretation-Version Recommendation

Production remains `portfolio-interpretation-v2` during PS-P9C.

If PS-P9D implements populated Setup, use `portfolio-interpretation-v3`. No
backfill; v0/v1/v2 snapshots remain immutable.

## 33. Explicit Owner Decisions

| Decision | Recommendation |
|---|---|
| `BREAKOUT` owner-facing label? | Yes, under L1 only. |
| `BREAKDOWN` owner-facing label? | Yes, as structural context only. |
| Structural rather than actionable? | Yes. |
| L1 agreement rule? | Approved and frozen. |
| OR15-only Setup allowed? | No. |
| OR30-only Setup allowed? | No. |
| Conflict -> null? | Yes. |
| Returned-inside -> null? | Yes. |
| Any-window returned-inside? | Yes, for required L1 windows. |
| Point-in-time intraday changes acceptable? | Yes. |
| Direct `BREAKOUT -> BREAKDOWN` acceptable? | Not needed for L1; replay found zero. If it appears later, prefer null between directions. |
| Post-close retain final-session Setup? | Yes, as latest-session structural snapshot. |
| Weekend/holiday retain latest-session Setup? | Yes, with provenance and no live-action implication. |
| Next-session hard reset? | Yes. |
| EntryQualification context only? | Yes. |
| VWAP context only? | Yes. |
| Intraday trend context only? | Yes. |
| RS/RVOL context only? | Yes. |
| Decision independent? | Yes. |
| D1 Trend independent? | Yes. |
| Conviction independent? | Yes. |
| Null reason taxonomy? | Approve. |
| No-setup vs unavailable distinction? | Mandatory. |
| Future implementation version? | `portfolio-interpretation-v3`. |
| PS-P9D or deferral? | PS-P9D implementation authorized after PS-P9C freeze. |

## 34. Recommended Next Milestone

PS-P9D: implement only L1 Opening Range Setup in Portfolio
interpretation/sync/API/dashboard using the existing `trend_setup`/
`trend_or_setup` surface, version new snapshots as `portfolio-interpretation-v3`,
and preserve Status, Action, Conviction, D1 Trend, Key Trigger, schema shape,
and all advisory-only boundaries.

## 35. Files Changed

Created:

- `docs/research/PS-P9C-PORTFOLIO-OPENING-RANGE-SETUP-LIFECYCLE-FREEZE.md`

Modified:

- `docs/research/PS-P9B-PORTFOLIO-OPENING-RANGE-SETUP-METHODOLOGY-REPLAY.md`
- `docs/MILESTONES.md`
- `IMPLEMENTATION_SUMMARY.md`
- `ATHENA_BRIEFING.md`

No production source files were changed for PS-P9C.

## 36. Validation

Documentation/research validation:

- `git diff --check`: clean.
- `uv.lock` status check: untouched.
- Production Portfolio Setup status check: still deferred/null.
- Portfolio interpretation version check: still `portfolio-interpretation-v2`.
- OpeningRangeEngine, EntryQualification, schema, API, and dashboard status
  checks: unchanged by PS-P9C.

## 38. Freeze Decision

PS-P9C is Owner / Chief Architect approved and frozen 2026-09-05. Candidate L1
is the only approved production Setup methodology for PS-P9D. L2 is rejected.
L3 remains a safe fallback if implementation is deferred, but is not the
preferred path.

## 37. Suggested Commit Message

```text
docs(portfolio): freeze Opening Range Setup lifecycle

- Mark PS-P9B owner-approved and frozen with production Setup still deferred.
- Add PS-P9C replay showing L1 OR15/OR30 agreement is a viable Setup method.
- Recommend PS-P9D implementation only after owner approval of L1 lifecycle.
```
