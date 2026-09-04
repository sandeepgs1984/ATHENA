# ATHENA Portfolio Sync - PS-P9A Portfolio Setup Methodology Discovery

**Date:** 2026-09-04
**Branch:** `feature/portfolio-sync`
**Milestone:** PS-P9A - discovery/methodology only
**Status:** Ready for Owner / Chief Architect review

---

## 1. Executive Summary

PS-P9A asked whether ATHENA can deterministically describe the current
actionable technical Setup of a holding using existing approved evidence,
without confusing Setup with the already-frozen D1 Trend or inventing new
thresholds.

Answer: not as a production Portfolio field yet.

ATHENA has relevant evidence, especially EntryQualification, TradePlan levels,
VWAP, intraday M5/M15 trend, RelativeStrength, RelativeVolume, and Opening Range
breakout measurements. But no existing approved core artifact currently owns a
Portfolio Setup taxonomy such as `BREAKOUT`, `PULLBACK`, `RETEST`,
`CONSOLIDATION`, `REVERSAL_ATTEMPT`, or `FAILED_STRUCTURE`.

Recommended outcome: keep Setup null/deferred in production and run PS-P9B as a
methodology-design/freeze milestone centered on whether Opening Range breakout
evidence plus EntryQualification context can support the smallest Setup
taxonomy. Do not implement Setup from PS-P9A.

## 2. Setup Semantic Recommendation

Setup should mean a specific current structural/actionability pattern, not a
directional trend state and not a trade instruction.

Recommended definition for future freeze:

> Portfolio Setup is a point-in-time, evidence-backed description of the
> current technical structure that explains how a holding may be actionable or
> not actionable now, independent of D1 Trend, Status, Next Action, Conviction,
> P&L, and TradePlan levels.

This definition is not implemented in PS-P9A.

## 3. Evidence Inventory

| Source | Existing artifact | Classification | PS-P9A finding |
|---|---|---|---|
| EntryQualification | `EntryQualification` state/reasons from persisted ID-6D output | APPROVED_CONTEXT_ONLY / RETRIEVABLE | Strong actionability context, but `QUALIFIED` means v0 readiness, not a Setup label. |
| TradePlan entry/stop/target | `TradePlan.entry_low`, `entry_high`, `stop_loss`, `targets` | APPROVED_CONTEXT_ONLY / RETRIEVABLE | Direct actionable levels; no pattern semantics. |
| Opening Range breakout | `OpeningRangeEvidence.breakout_event`, relation, extension | APPROVED_CONTEXT_ONLY / ADAPTER_REQUIRED / REPLAY_REQUIRED | Closest approved breakout measurement; not yet a Portfolio Setup method. |
| VWAP | `VwapEvidence` relation/deviation | APPROVED_CONTEXT_ONLY / ADAPTER_REQUIRED | Useful same-session location/readiness evidence; not a standalone Setup label. |
| Intraday trend | `IntradayTrendContext` M5/M15 aggregate | APPROVED_CONTEXT_ONLY / ADAPTER_REQUIRED | Actionability nuance; must not override D1 Trend or become Setup by itself. |
| RelativeStrength | `RelativeStrengthContext` stock-vs-sector/market relations | APPROVED_CONTEXT_ONLY / ADAPTER_REQUIRED | Participation/context only; not a pattern. |
| RelativeVolume | `RelativeVolumeContext` same-time cumulative volume relation | APPROVED_CONTEXT_ONLY / ADAPTER_REQUIRED | Confirmation/context only; no surge label or Setup label. |
| Gap | `GapContext` previous-close to current-open transition | APPROVED_CONTEXT_ONLY / ADAPTER_REQUIRED | Session-open context only; no gap-fill/hold/rejection semantics. |
| Technical structure score | `ScoringEngine._technical_structure` component | RETRIEVABLE / METHODOLOGY_REQUIRED | Numeric score using SMA/MACD/VWAP; not a Setup vocabulary. |
| ScoringResult components | `trend`, `momentum`, `technical_structure`, etc. | RETRIEVABLE / METHODOLOGY_REQUIRED | Composite inputs are not labels and risk double-counting. |
| DecisionReport evidence | persisted run detail / report blocks | RETRIEVABLE / ADAPTER_REQUIRED | May expose context, but no canonical Setup field found. |
| Regime context | market/index trend labels | APPROVED_CONTEXT_ONLY | Market context only; never holding Setup. |
| Swing/pivot/high-low structure | no approved core Portfolio artifact found | NOT_AVAILABLE / METHODOLOGY_REQUIRED | Needs explicit methodology before use. |
| Support/resistance | TradePlan stop/target only in current core | METHODOLOGY_REQUIRED | No general support/resistance model is approved for Portfolio Setup. |
| Consolidation/range | OR formation boundaries only; DarvaX boxes isolated | METHODOLOGY_REQUIRED / EXPERIMENTAL | No approved consolidation/range Setup semantics. |
| DarvaX | isolated experimental satellite box/breakout/retest system | EXPERIMENTAL | Excluded from core Portfolio unless separately promoted by owner. |
| Explosive Move / EMR | isolated research/live-shadow artifacts | EXPERIMENTAL | Excluded from Portfolio Setup unless separately promoted by owner. |

## 4. EntryQualification Findings

EntryQualification answers whether an already-produced canonical Decision is
intraday-actionable now. Its frozen v0 formula is:

`VWAP positive AND aggregate intraday trend BULLISH AND (RS support OR RVOL support)`.

It does not distinguish `BREAKOUT`, `PULLBACK`, `RETEST`, `CONSOLIDATION`, or
`FAILED_STRUCTURE`. `QUALIFIED` must not be mapped directly to `BREAKOUT`.

Recommendation: treat EntryQualification as context/confirmation only for a
future Setup methodology.

## 5. TradePlan Findings

The current TradePlan is a daily-only ATR construct attached only to `TRADE`
Decisions. Entry is currently the latest D1 close; stop and target are ATR
multiples. It does not consume EntryQualification, ORB, RelativeStrength,
RelativeVolume, or intraday Setup evidence.

Do not infer:

- price below `entry_low` -> `PULLBACK`
- price inside entry band -> `RETEST`
- price above `entry_high` -> `BREAKOUT`

Recommendation: TradePlan is context and level provenance only.

## 6. Breakout Findings

ATHENA does have a real approved breakout measurement in Opening Range evidence:
`BreakoutEvent.UPSIDE_BREAKOUT_EVENT` / `DOWNSIDE_BREAKDOWN_EVENT` over OR15 and
OR30. It is session-scoped, M5-based, canonical-slot filtered, completed-candle
safe, and deterministic.

However, the artifact explicitly says measurements only: no BUY/SELL, no entry
zone, no confirmation rule, no strength label, and no trade meaning. ID-6B also
kept OR15/OR30 contextual rather than making them v0 EntryQualification gates.

Recommendation: `BREAKOUT` is the strongest candidate, but it is
`ADAPTER_REQUIRED`, `METHODOLOGY_REQUIRED`, and `REPLAY_REQUIRED` before any
Portfolio Setup implementation.

## 7. Pullback Findings

No approved core artifact currently defines a pullback. Potential ingredients
exist, such as D1 Trend, VWAP relation, moving averages, TradePlan entry, or
opening-range relation, but no approved rule distinguishes a pullback from
ordinary price location.

Recommendation: `PULLBACK` is `METHODOLOGY_REQUIRED` and `REPLAY_REQUIRED`.

## 8. Retest Findings

DarvaX has a breakout/retest state machine, but DarvaX is an isolated
experimental satellite and cannot be silently promoted into core Portfolio.
Core ATHENA Opening Range can detect returned-inside-range after an OR breakout,
but no approved Portfolio retest definition exists.

Recommendation: `RETEST` is `METHODOLOGY_REQUIRED`; DarvaX remains excluded.

## 9. Consolidation Findings

Trend `MIXED` is not consolidation. Opening Range has range boundaries for the
opening window only; DarvaX boxes are isolated; EMR has range/compression
features in research artifacts. None is approved as a Portfolio consolidation
Setup.

Recommendation: `CONSOLIDATION`/`BASE` is `METHODOLOGY_REQUIRED` and likely
needs explicit range persistence, compression, and invalidation semantics before
any implementation.

## 10. Failed-Structure Findings

Portfolio already has `AT_RISK`/`EXIT` when the coherent TradePlan stop is
breached. Relabeling stop breach as `FAILED_STRUCTURE` would duplicate Status
and Next Action unless a separate structural-failure methodology is approved.

Recommendation: defer `FAILED_STRUCTURE`; classify as potentially useful only
if future PS-P9B can define it independently of stop breach and D1 downtrend.

## 11. D1 / Intraday Recommendation

Unlike Trend, Setup probably cannot be D1-only if the intended meaning is
"current actionable pattern." The most promising evidence is intraday and
session-scoped: Opening Range, VWAP, M5/M15 trend, RelativeStrength, and
RelativeVolume.

Recommendation: allow intraday participation in future Setup methodology, but
only with explicit market-hours, post-close, weekend/holiday, stale/missing, and
replay semantics. If the owner wants a stable end-of-day Setup label, that
should be a separate D1-only design, not mixed into the intraday meaning.

## 12. Trend Relationship

Trend and Setup remain independent:

- `UPTREND` does not imply `BREAKOUT`.
- `DOWNTREND` does not imply `FAILED_STRUCTURE`.
- `MIXED` does not imply `CONSOLIDATION`.

D1 Trend may be context for future Setup explanations, but it should not map
directly to a Setup value.

## 13. Key Trigger Relationship

Key Trigger already exposes the coherent active TradePlan entry trigger when
price is below `entry_low`. Setup should not duplicate that level. If future
Setup says `BREAKOUT`, it must explain a structural event or current pattern
that is distinct from "entry trigger still available."

## 14. Conviction Relationship

Conviction remains independent. A future Setup could be `BREAKOUT` with LOW
Conviction or `PULLBACK` with HIGH Conviction. Conviction measures Decision
confidence/reliability, not structure.

## 15. Status / Action Relationship

PS-P9A recommends Setup remain display/explanation intelligence only in its
first implementation. It must not silently become an additional ADD gate, EXIT
gate, or Status override.

## 16. Experimental Evidence Classification

DarvaX, EMR, and other satellite/research artifacts are excluded from core
Portfolio Setup until the owner explicitly promotes them through a separate
methodology and architecture review. They may be cited as inspiration only.

## 17. Candidate Taxonomy

Smallest viable future taxonomy should start no larger than:

- `BREAKOUT`
- `null`

Only if PS-P9B finds explicit approved evidence should it consider adding:

- `PULLBACK`
- `RETEST`
- `CONSOLIDATION` / `BASE`
- `REVERSAL_ATTEMPT`
- `FAILED_STRUCTURE`

PS-P9A does not approve any label for production.

## 18. Lifecycle Recommendation

Setup is likely transient and session-scoped. Future methodology must define:

- when the setup becomes observable;
- whether it is candidate/confirmed/consumed/failed;
- what invalidates it;
- whether it can reappear in the same session;
- post-close behavior;
- whether old snapshots preserve a consumed setup or only the point-in-time
  label.

No lifecycle state is approved in PS-P9A.

## 19. Missing / Stale Semantics

Recommended future default:

- missing required evidence -> Setup null;
- stale/incoherent evidence -> Setup null;
- unavailable intraday evidence -> Setup null if intraday is required;
- no `UNKNOWN` display value in the owner-facing field unless separately
  approved;
- no fallback from Trend, DecisionType, Status, Action, Conviction, P&L, or
  stale TradePlan.

## 20. Replay Recommendation

Replay is mandatory before Setup implementation. Setup is more transient and
more semantically nuanced than Trend.

Replay should report:

- classification frequency;
- persistence and transition behavior;
- consumed/invalidated states if any;
- pathological flip-flops;
- deterministic equality;
- future-leakage checks;
- missing/stale/incoherent distributions;
- representative human-review examples with symbol, session, D1 Trend, Setup
  candidate, EntryQualification, TradePlan, Conviction, Decision, and reasons.

Do not invent acceptance percentages in PS-P9A.

## 21. Candidate Classification Table

| Candidate | Classification | Recommendation |
|---|---|---|
| `BREAKOUT` | ADAPTER_REQUIRED / METHODOLOGY_REQUIRED / REPLAY_REQUIRED | Strongest PS-P9B candidate using Opening Range evidence plus context. |
| `PULLBACK` | METHODOLOGY_REQUIRED / REPLAY_REQUIRED | Do not implement without a frozen definition. |
| `RETEST` | METHODOLOGY_REQUIRED / EXPERIMENTAL / REPLAY_REQUIRED | Core evidence insufficient; DarvaX excluded. |
| `CONSOLIDATION` | METHODOLOGY_REQUIRED / EXPERIMENTAL / REPLAY_REQUIRED | Do not derive from Trend `MIXED`. |
| `BASE` | METHODOLOGY_REQUIRED / EXPERIMENTAL / REPLAY_REQUIRED | Same as consolidation/range. |
| `REVERSAL_ATTEMPT` | METHODOLOGY_REQUIRED / REPLAY_REQUIRED | No approved core semantic found. |
| `FAILED_STRUCTURE` | DEFER / METHODOLOGY_REQUIRED | Risk of duplicating Status/EXIT/stop breach. |
| `null` | READY_FROM_EXISTING_APPROVED_EVIDENCE | Continue current deferred behavior. |

## 22. Interpretation Version Recommendation

Keep production at `portfolio-interpretation-v2` during PS-P9A.

If a future milestone implements populated Setup semantics, recommend
`portfolio-interpretation-v3` because an owner-facing field that was explicitly
deferred/null gains methodology.

## 23. Explicit Owner Decisions / Recommendations

| Decision | PS-P9A recommendation |
|---|---|
| What exactly should Setup mean? | A current structural/actionability pattern, not direction, confidence, status, action, or P&L. |
| D1 only or may intraday participate? | May intraday participate, with explicit session/freshness/replay rules. |
| Is EntryQualification a Setup source? | Context/confirmation only, not direct label source. |
| Is TradePlan a Setup source? | Context/levels only, not direct label source. |
| Is BREAKOUT supportable now? | Evidence exists, but production label needs PS-P9B freeze/replay. |
| Is PULLBACK supportable now? | No; methodology required. |
| Is RETEST supportable now? | No; methodology required; DarvaX excluded. |
| Is CONSOLIDATION supportable now? | No; methodology required; never infer from `MIXED`. |
| Is FAILED_STRUCTURE useful? | Possibly, but likely redundant unless separately defined. |
| Is DarvaX excluded? | Yes. |
| Are research/satellite modules excluded? | Yes, unless separately promoted. |
| Proposed smallest taxonomy? | Start with `BREAKOUT`/`null` for PS-P9B investigation. |
| Exact lifecycle semantics? | Not approved; PS-P9B must define them. |
| Missing/stale -> null? | Yes. |
| Replay required before implementation? | Yes. |
| Future Setup version? | `portfolio-interpretation-v3`. |
| Smallest PS-P9B? | Methodology design/freeze and replay for Opening Range breakout-based Setup. |
| If insufficient? | Keep Setup deferred and move to Support 1 or historical analytics. |

## 24. Smallest PS-P9B Recommendation

Recommended next milestone:

**PS-P9B - Portfolio Setup Methodology Design / Replay Contract**

Scope:

- decide whether Opening Range breakout can become Portfolio `BREAKOUT`;
- define exact OR15/OR30 precedence;
- define confirmation/context role of EntryQualification, VWAP, intraday trend,
  RS, and RVOL;
- define lifecycle and missing/stale/null semantics;
- create replay and human-review pack requirements;
- do not implement production Setup yet.

## 25. Files Changed

Created:

- `docs/research/PS-P9A-PORTFOLIO-SETUP-METHODOLOGY-DISCOVERY.md`

Modified:

- `docs/MILESTONES.md`
- `IMPLEMENTATION_SUMMARY.md`
- `ATHENA_BRIEFING.md`
- `docs/research/PS-P8C-PORTFOLIO-D1-TREND-ADAPTER-IMPLEMENTATION.md`

No production source files were changed for PS-P9A.

## 26. Validation

Documentation-only validation:

- `git diff --check`: clean.
- source status check: no production source files changed by PS-P9A.
- schema/API/dashboard status check: no PS-P9A schema, API, or dashboard
  changes.
- `uv.lock` status check: untouched.
- Portfolio interpretation version check: production remains
  `portfolio-interpretation-v2`; PS-P9A only recommends
  `portfolio-interpretation-v3` if a future milestone implements populated
  Setup semantics.

## 27. Suggested Commit Message

```text
docs(portfolio): discover Portfolio Setup methodology

- Mark PS-P8C owner-approved and frozen after final future-evidence hardening.
- Add PS-P9A discovery showing Setup has no safe production methodology yet.
- Recommend a PS-P9B methodology/replay contract before any Setup implementation.
```
