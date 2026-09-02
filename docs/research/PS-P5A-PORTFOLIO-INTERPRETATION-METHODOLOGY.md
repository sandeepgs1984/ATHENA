# PS-P5A Portfolio Interpretation Methodology

Status: Ready for Owner/Chief Architect methodology review
Date: 2026-09-02
Scope: Evidence inventory and deterministic methodology proposal only
Boundary: No production interpreter, no Portfolio Sync wiring, no dashboard
changes, no ScoringEngine/DecisionEngine/indicator changes, no order placement

## 1. Executive Summary

PS-P5A defines the proposed Portfolio Interpretation layer for My Portfolio.
The layer answers a portfolio-specific question: given an already-held
instrument, current owner holding facts, and coherent persisted ATHENA evidence,
what should the Portfolio Snapshot say about holding health, confidence,
structure, levels, targets, and owner action?

The recommendation is conservative. PS-P5B should implement only fields that
are supportable by already-approved, retrievable evidence:

- Status: derived portfolio health vocabulary.
- Conviction: direct mapping from approved ATHENA confidence when available.
- Trend / Setup: concise mapping from approved trend/setup evidence.
- Major Support / Exit: TradePlan stop-loss only when the coherent Decision has
  an active TradePlan.
- Next Action: HOLD / ADD / REDUCE / EXIT / WATCH, with ADD kept strict.

Support 1 and Target 2/3 should remain nullable in PS-P5B unless the owner
approves a separate support/target methodology or an already-approved retrievable
source is wired into Portfolio Sync.

## 2. Scope

PS-P5A includes:

- source inspection of current ATHENA evidence artifacts
- an evidence matrix for each Portfolio Snapshot interpretation field
- proposed typed input/output concepts
- proposed deterministic rule matrices
- reason-code design
- deterministic test vectors for PS-P5B
- explicit owner decisions required before implementation

PS-P5A does not implement production interpretation.

## 3. Frozen Architectural Boundaries

PS-P5A preserves the PS-P0 through PS-P4.1 architecture:

- My Portfolio remains an isolated ATHENA subdomain.
- `portfolio_holdings` is the only source of current holdings.
- Portfolio Sync consumes persisted ATHENA evidence; it does not feed back into
  ScoringEngine, DecisionEngine, indicators, provider adapters, or core runs.
- `owner_positions` remains separate.
- quantity, average price, imported-at, and owner cost basis remain portfolio
  facts, not signal-quality inputs.
- snapshots remain immutable per sync run.
- PS-P4.1 freshness and Decision/TradePlan coherency remain mandatory.
- no transaction inference, broker logic, realized P&L reconstruction, or order
  placement is introduced.

## 4. Existing ATHENA Evidence Inventory

| Evidence | Current implementation | Portfolio usefulness | Direct / Derived / Missing | Methodological risk |
|---|---|---|---|---|
| `Decision` | Persisted in `decisions`; fields include `decision_type`, explanation, gates, refs, optional `TradePlan` | Primary current ATHENA recommendation artifact | Direct | Must not alias DecisionType directly into portfolio Status |
| `DecisionType` | `TRADE`, `WATCH`, `NO_TRADE`, `INSUFFICIENT_DATA`, etc. through `DecisionEngine` | One input to portfolio health/action | Derived | Entry recommendation semantics differ from holding semantics |
| Decision explanation | Persisted on `Decision` | Audit and UI explanation source | Direct | Long prose is not a methodology source |
| Quality gates | Persisted as `Decision.gate_results` | Detect blocked evidence/risk/confidence/market states | Direct | Gate failure reason is not always structural deterioration |
| Composite score | `ScoringResult.composite`; Decision stores `score_ref` but no retrievable score table found | Could help Status only if resolved | Missing for PS-P5B unless evidence adapter is extended | Do not infer score from Decision explanation |
| Confidence | `ConfidenceAssessment` has `overall_level` LOW/MEDIUM/HIGH; no retrievable confidence table found | Best semantic match for Conviction | Missing unless persisted/resolved; direct if available | Do not invent confidence from P&L |
| Risk | `RiskAssessment` has `overall_level`; Decision stores `risk_ref` only | Could inform CAUTION/AT_RISK | Missing unless persisted/resolved | Risk is exposure/uncertainty, not a sell signal by itself |
| TradePlan entry | `TradePlan.entry_low`/`entry_high` on TRADE only | Possible active trigger if still within validity and not already stale | Direct when coherent | Historical entry trigger can become stale after price moves |
| TradePlan stop | `DecisionEngine` builds stop from last close +/- ATR stop multiple | Legitimate risk-control/invalidation level for coherent TRADE | Direct | Not a general Support 1 model |
| TradePlan targets | `targets` tuple on TRADE, currently built as one ATR target | Target 1 direct; T2/T3 unavailable today | Direct for T1, missing for T2/T3 | Do not fabricate ladders |
| Risk/reward | Derived from ATR target/stop distance | Audit only | Direct | Not enough to classify health alone |
| Regime trend | `RegimeResult` labels: BULL_TREND, BEAR_TREND, SIDEWAYS, TREND_UNKNOWN | Generic trend input | Derived | Market/index regime is not instrument-specific setup |
| Scoring trend component | score dimension `trend` uses regime trend + ADX + confluence | Better trend-strength input if retrievable | Missing unless resolved | Numeric score is not a label vocabulary by itself |
| Technical structure component | price-vs-SMA + MACD + VWAP contribution | Best existing generic structure source | Missing unless resolved | Does not expose support levels |
| Market health | `MarketHealthScore` and labels consumed by scoring/risk/decision | Context / conflict input | Missing in snapshot unless retrieved separately | Adverse market does not automatically break one holding |
| Sector health | `SectorHealthResult` and sector score labels | Context / conflict input | Missing in snapshot unless retrieved separately | Sector context should not override instrument evidence blindly |
| Relative strength | `RelativeStrengthContext` relations OUTPERFORMING / UNDERPERFORMING / MATCHING / UNKNOWN | Useful support/conflict evidence | Missing from current Portfolio Sync, persisted only indirectly if EntryQualification refs are used | Zero-threshold relation, not strong/weak bands |
| RVOL | `RelativeVolumeContext` ABOVE/BELOW/AT_BASELINE/UNKNOWN | Actionability support evidence | Missing from current Portfolio Sync, indirect via EntryQualification | Volume support is not structural invalidation |
| Intraday trend | `IntradayTrendContext` BULLISH/BEARISH/MIXED/UNKNOWN | Add-readiness/setup nuance | Missing unless latest EntryQualification or signal set is resolved | Provisional live M5 finality must be explicit |
| VWAP | `VwapEvidence` ABOVE/BELOW/AT/UNAVAILABLE | Add-readiness/setup nuance | Missing unless latest EntryQualification or signal set is resolved | Same-session only |
| Opening range | OR15/OR30 measurements and breakout events | Potential setup/trigger evidence | Missing in current Portfolio Sync | Contextual only; no approved portfolio action rule |
| Gap | `GapContext` descriptive D1 open gap | Context only | Missing | Not action by itself |
| EntryQualification | Persisted after ID-6D; state QUALIFIED/NOT_YET/UNKNOWN/etc. for WATCH/TRADE | Best approved input for strict ADD readiness | Direct if latest coherent row is read in PS-P5B | Actionability is point-in-time and may flicker |
| DarvaX signal | Satellite-only, experimental unvalidated, disjoint from ATHENA Decision | Adjacent structural levels exist | Deferred | ADR-010 says ATHENA cannot read DarvaX as core evidence without approval |
| Freshness/session provenance | PS-P4.1 `expected_analysis_as_of`, `price_as_of`, `decision_as_of` | Required gate for all interpretation | Direct | Stale evidence must produce null/WATCH, not a confident label |

## 5. Evidence Gaps

The current repository persists Decisions, traces, candles, and
EntryQualification observations. It does not appear to persist fully
rehydratable ScoringResult, ConfidenceAssessment, RiskAssessment, IndicatorSet,
RegimeResult, SectorHealthResult, RelativeStrengthContext, RelativeVolumeContext,
OpeningRangeEvidence, or IntradaySignalSet as first-class ATHENA core artifacts
that Portfolio Sync can read by `Decision.score_ref` / `confidence_ref` /
`risk_ref`.

That limits PS-P5B unless it also adds a narrow, approved evidence adapter. The
minimal implementable PS-P5B should consume:

- coherent `Decision`
- coherent `TradePlan`
- `Decision.gate_results`
- `Decision.decision_type`
- persisted latest coherent `EntryQualification`, only for ADD readiness
- owner holding facts and PS-P4.1 freshness facts

## 6. Interpretation Layer Semantics

Proposed typed concepts:

`PortfolioAnalysisEvidence`

- holding facts: quantity, average price, last price, unrealized P&L percent
- freshness: expected analysis session, price session, decision session
- decision: type, gates, explanation, refs
- trade plan: entry range, stop, targets, validity
- optional entry qualification: state, finality, reason codes

`PortfolioInterpretation`

- status
- conviction
- trend_setup
- key_trigger
- support_1
- major_support_exit
- target_2
- target_3
- next_action
- reason codes
- interpretation version

The interpreter should be pure and side-effect free.

## 7. Status Definition

Proposed vocabulary:

- `STRONG`: holding is technically healthy and has coherent actionable support.
- `HEALTHY`: structure is intact enough to hold, but no stronger add/readiness
  conclusion is supported.
- `CAUTION`: evidence is incomplete, blocked, conflicting, or deteriorating, but
  no approved invalidation/exit condition is triggered.
- `AT_RISK`: an approved invalidation/risk-control level is breached or current
  coherent evidence says the holding thesis is materially broken.
- `UNAVAILABLE`: current price or coherent evidence is missing.

## 8. Status Rule Matrix

Precedence, highest first:

| Condition | Status | Reason codes |
|---|---|---|
| No current price or price session not current enough | `UNAVAILABLE` | `PRICE_UNAVAILABLE` / `STALE_PRICE_SESSION` |
| No coherent current Decision | `UNAVAILABLE` | `NO_CURRENT_DECISION` / `STALE_DECISION_EVIDENCE` |
| Long holding with coherent TradePlan stop and `last_price <= stop_loss` | `AT_RISK` | `MAJOR_INVALIDATION_BREACHED`, `TRADE_PLAN_STOP_BREACHED` |
| DecisionType is `INSUFFICIENT_DATA` | `UNAVAILABLE` | `INSUFFICIENT_DECISION_DATA` |
| Any current gate failure on DATA or EVIDENCE | `CAUTION` | `DECISION_GATE_FAILED_DATA` / `DECISION_GATE_FAILED_EVIDENCE` |
| Any current gate failure on RISK, CONFIDENCE, or MARKET | `CAUTION` | corresponding gate reason |
| DecisionType is `NO_TRADE` | `CAUTION` | `NO_TRADE_DECISION_EVIDENCE` |
| Latest coherent EntryQualification is `QUALIFIED` and DecisionType is WATCH or TRADE | `STRONG` | `ENTRY_QUALIFICATION_READY`, `STRUCTURE_SUPPORTED` |
| DecisionType is `TRADE` with active coherent TradePlan and no failed gates | `STRONG` | `CURRENT_TRADE_PLAN`, `ALL_DECISION_GATES_PASSED` |
| DecisionType is `WATCH` with no failed gates | `HEALTHY` | `WATCH_STRUCTURE_INTACT` |
| Otherwise coherent but not stronger | `HEALTHY` | `STRUCTURE_INTACT` |

This is not DecisionType aliasing: STOP breach, freshness, gates, and optional
EntryQualification have precedence over the raw DecisionType label.

## 9. Conviction Definition

Conviction means the reliability/consistency of ATHENA evidence supporting the
portfolio interpretation. It does not mean expected profit, owner confidence,
or unrealized P&L.

## 10. Conviction Mapping

Preferred mapping:

- If a coherent `ConfidenceAssessment.overall_level` is retrievable, map it
  directly to `HIGH` / `MEDIUM` / `LOW`.
- If confidence is not retrievable in PS-P5B, leave Conviction null rather than
  deriving it from DecisionType, P&L, or score refs.

Reason codes:

- `CONFIDENCE_DIRECT_HIGH`
- `CONFIDENCE_DIRECT_MEDIUM`
- `CONFIDENCE_DIRECT_LOW`
- `CONFIDENCE_EVIDENCE_UNAVAILABLE`

Owner decision required: whether PS-P5B should add an evidence adapter to
retrieve confidence, or keep Conviction nullable for the first implementation.

## 11. Trend / Setup Mapping

Preferred source order:

1. Current approved setup artifact if a retrievable one exists.
2. Latest coherent EntryQualification plus intraday evidence refs, only for
   `Add Readiness` style labels.
3. Decision explanation/gates are not parsed for setup labels.

Recommended PS-P5B minimal mapping:

- `Add Ready`: latest coherent EntryQualification is `QUALIFIED`.
- `Watchlist Setup`: coherent DecisionType is `WATCH` and no stronger setup is
  retrievable.
- `Trade Setup`: coherent DecisionType is `TRADE` with active TradePlan, if no
  more specific setup is retrievable.
- null when evidence is insufficient or stale.

Generic labels like Uptrend, Pullback, Range, Breakout Retest, and Weakening
Trend should remain deferred unless a typed source is made available. Do not
parse prose or derive chart patterns from candles inside Portfolio Sync.

## 12. Key Trigger Mapping

Allowed sources:

- coherent active TradePlan entry range for a current TRADE decision
- future approved EntryQualification/add trigger artifact, if added

Proposed behavior:

- If latest price is below `entry_low`, `key_trigger = entry_low`.
- If latest price is inside `[entry_low, entry_high]`, `key_trigger = entry_high`
  or the single-point entry when equal.
- If latest price is above `entry_high`, the historical entry trigger is already
  consumed and `key_trigger = null`.
- If the TradePlan is outside its validity window, `key_trigger = null`.

Reason codes:

- `TRADE_PLAN_ENTRY_TRIGGER_ACTIVE`
- `ENTRY_TRIGGER_ALREADY_CONSUMED`
- `TRADE_PLAN_EXPIRED`
- `NO_ACTIVE_TRIGGER_EVIDENCE`

## 13. Support 1 Analysis

Finding: current ATHENA core does not expose a retrievable approved Support 1
contract. SMA, previous-day low, arbitrary pivots, OR lows, and DarvaX box
floors are not approved as Portfolio Support 1 sources inside ATHENA core.

Recommendation: keep `support_1 = null` in PS-P5B with
`SUPPORT_1_METHODOLOGY_UNAVAILABLE`.

## 14. Major Support / Exit Analysis

Finding: coherent TradePlan stop-loss is an approved risk-control/invalidation
level for a TRADE decision. It is not Support 1, but it can populate Major
Support / Exit for long holdings when:

- the Decision/TradePlan passes PS-P4.1 coherency
- the TradePlan is within `valid_from` / `valid_until`
- the holding direction is LONG or the plan direction is explicitly LONG

If no coherent active TradePlan exists, keep the field null.

## 15. Target 1 Validation

PS-P4.1 Target 1 mapping remains valid: it maps only from coherent
`TradePlan.targets[0]`. PS-P5B should preserve this rule unchanged.

## 16. Target 2/3 Analysis

Finding: current DecisionEngine builds a single target from ATR target multiple.
No approved ATHENA core target ladder was found.

Recommendation: keep `target_2 = null` and `target_3 = null` with
`NO_APPROVED_SECONDARY_TARGET`.

## 17. Next Action Vocabulary

Proposed PS-P5B vocabulary:

- `HOLD`
- `ADD`
- `REDUCE`
- `EXIT`
- `WATCH`

`ROTATE` remains deferred because it requires comparative opportunity and
capital-allocation intelligence beyond this milestone.

## 18. Next Action Rule Matrix

Precedence, highest first:

| Condition | Next Action | Reason codes |
|---|---|---|
| Missing/stale price or missing/stale coherent Decision | `WATCH` | `INSUFFICIENT_CURRENT_EVIDENCE` |
| Major Support / Exit breached | `EXIT` | `MAJOR_INVALIDATION_BREACHED` |
| DecisionType `NO_TRADE` or DATA/EVIDENCE gate failed | `REDUCE` if owner approves; otherwise `WATCH` | `STRUCTURE_DETERIORATING` |
| RISK/CONFIDENCE/MARKET gate failed but no invalidation | `WATCH` | `CONTEXT_CAUTION` |
| EntryQualification `QUALIFIED` and active TradePlan exists | `ADD` | `ENTRY_QUALIFICATION_READY`, `CURRENT_TRADE_PLAN` |
| DecisionType `TRADE` with active TradePlan, but no EntryQualification | `HOLD` | `CURRENT_TRADE_PLAN`, `ADD_NOT_CONFIRMED` |
| DecisionType `WATCH` and no failed gates | `HOLD` | `WATCH_STRUCTURE_INTACT` |
| Otherwise coherent but not actionable | `WATCH` | `NO_STRONGER_ACTION_SUPPORTED` |

ADD is intentionally strict. A raw TRADE decision alone should not recommend
adding to an existing position unless the owner approves that lower bar.

## 19. Reason Codes

Proposed initial enum values:

- `PRICE_UNAVAILABLE`
- `STALE_PRICE_SESSION`
- `NO_CURRENT_DECISION`
- `STALE_DECISION_EVIDENCE`
- `INSUFFICIENT_DECISION_DATA`
- `DECISION_GATE_FAILED_DATA`
- `DECISION_GATE_FAILED_EVIDENCE`
- `DECISION_GATE_FAILED_RISK`
- `DECISION_GATE_FAILED_CONFIDENCE`
- `DECISION_GATE_FAILED_MARKET`
- `NO_TRADE_DECISION_EVIDENCE`
- `WATCH_STRUCTURE_INTACT`
- `CURRENT_TRADE_PLAN`
- `ALL_DECISION_GATES_PASSED`
- `ENTRY_QUALIFICATION_READY`
- `ADD_NOT_CONFIRMED`
- `TRADE_PLAN_ENTRY_TRIGGER_ACTIVE`
- `ENTRY_TRIGGER_ALREADY_CONSUMED`
- `TRADE_PLAN_EXPIRED`
- `TRADE_PLAN_STOP_BREACHED`
- `MAJOR_INVALIDATION_BREACHED`
- `SUPPORT_1_METHODOLOGY_UNAVAILABLE`
- `NO_APPROVED_SECONDARY_TARGET`
- `CONFIDENCE_EVIDENCE_UNAVAILABLE`
- `CONTEXT_CAUTION`
- `STRUCTURE_DETERIORATING`
- `NO_STRONGER_ACTION_SUPPORTED`

## 20. Null / Unavailable Semantics

Null remains valid and preferred over false precision.

- `conviction`: null unless confidence is retrievable.
- `trend_setup`: null unless a typed supported source exists.
- `key_trigger`: null when no active approved trigger exists.
- `support_1`: null in PS-P5B unless separate methodology is approved.
- `major_support_exit`: null without coherent active TradePlan stop.
- `target_2` / `target_3`: null until approved target ladder exists.

## 21. Conflict Resolution / Precedence

Global precedence:

1. Freshness/coherency failure.
2. Explicit invalidation/stop breach.
3. Insufficient data.
4. Failed DATA/EVIDENCE gates.
5. Failed RISK/CONFIDENCE/MARKET gates.
6. Current EntryQualification readiness.
7. Current TradePlan.
8. WATCH/healthy structure.
9. Null/WATCH fallback.

Conflicts:

- Positive Decision + weak RS: no automatic downgrade unless RS is available
  through EntryQualification or future explicit evidence adapter.
- Strong score + adverse market gate: CAUTION/WATCH wins because gate failure is
  part of the Decision contract.
- Healthy trend + NO_TRADE: CAUTION, because core Decision says the setup is
  not watch/trade quality today.
- TradePlan current + structure weakening: do not ADD; HOLD/WATCH/REDUCE based
  on gate and owner approval.
- No Decision + valid price: valuation succeeds; interpretation fields stay
  null or action WATCH.

## 22. Interpretation Versioning

Proposed methodology identifier:

`portfolio-interpretation-v0`

PS-P5B should persist this in snapshot provenance or analysis version metadata
without mutating previous snapshots.

## 23. Deterministic Test Vectors

| Scenario | Inputs | Expected proposal |
|---|---|---|
| A current TRADE + active TradePlan + EntryQualification QUALIFIED | coherent price/decision, all gates pass, plan active, price not below stop | Status STRONG, Next Action ADD, Target 1 mapped, Major Support / Exit stop, Support 1 null, T2/T3 null |
| B WATCH + no failed gates + no TradePlan | coherent current price/decision | Status HEALTHY, Next Action HOLD, Target 1 null, Major Support / Exit null |
| C NO_TRADE + coherent current price | no TradePlan | Status CAUTION, Next Action WATCH or REDUCE pending owner decision |
| D valid current price + no coherent Decision | price row succeeds | Status UNAVAILABLE, Conviction null, Next Action WATCH, all Decision-derived levels null |
| E TRADE + RISK gate failed | no TradePlan if DecisionEngine emitted WATCH/NO_TRADE, or non-TRADE blocked state | Status CAUTION, Next Action WATCH, no ADD |
| F current TradePlan with one target | `targets=(t1,)` | Target 1 populated, Target 2/3 null |
| G no support methodology | any otherwise coherent row | Support 1 null with `SUPPORT_1_METHODOLOGY_UNAVAILABLE` |
| H price <= coherent stop | long holding, active TradePlan | Status AT_RISK, Next Action EXIT, Major Support / Exit populated |
| I price above entry_high | active TradePlan | Key Trigger null with `ENTRY_TRIGGER_ALREADY_CONSUMED` |

## 24. Methodology Risks

- Conviction cannot be truthfully populated unless confidence artifacts are
  retrievable or a new approved evidence adapter is added.
- Status based only on Decision/gates/TradePlan is useful but thinner than a
  full technical-structure interpretation.
- REDUCE may be too action-oriented without a validated intermediate
  deterioration rule.
- ADD may over-encourage pyramiding unless gated by EntryQualification and
  active TradePlan.
- DarvaX levels are tempting but explicitly disjoint and experimental today.

## 25. Fields Ready for Implementation

Ready with current persisted evidence:

- Status, using conservative Decision/gate/TradePlan/EntryQualification rules.
- Major Support / Exit, from coherent active TradePlan stop.
- Target 1, unchanged from PS-P4.1.
- Target 2/3 null reason codes.
- Support 1 null reason code.
- Next Action, if owner approves vocabulary and REDUCE/ADD strictness.

Ready only if evidence adapter is approved:

- Conviction from ConfidenceAssessment.
- richer Trend / Setup from typed structure/intraday evidence.
- Key Trigger from richer add-trigger artifacts.

## 26. Fields Still Requiring Methodology

- Support 1: no approved ATHENA core source found.
- Target 2/3: no approved target ladder found.
- ROTATE: requires comparative opportunity and capital context.
- REDUCE: owner must decide whether gate-driven deterioration is sufficient.
- Conviction: owner must decide whether to add confidence retrieval or keep null.

## 27. Proposed PS-P5B Scope

Recommended PS-P5B should:

- add typed `PortfolioAnalysisEvidence` and `PortfolioInterpretation`
- add a pure deterministic interpreter for the approved subset
- keep PS-P4.1 freshness/coherency checks as a hard precondition
- optionally read latest coherent `EntryQualification` for ADD readiness
- wire outputs into Portfolio Snapshot rows
- persist reason codes in existing provenance/unavailable metadata or an
  approved narrow extension
- add unit tests for the matrix above and integration tests through Sync

It should not add support-level discovery, target ladder generation, DarvaX
integration, score/confidence/risk persistence, or dashboard redesign unless
explicitly approved.

## 28. Explicit Owner Decisions Required

1. Approve final Status vocabulary: STRONG / HEALTHY / CAUTION / AT_RISK /
   UNAVAILABLE?
2. Approve Status precedence table?
3. Should Conviction map directly from ConfidenceAssessment if retrievable, and
   stay null otherwise?
4. Should PS-P5B add a confidence evidence adapter, or defer Conviction?
5. Approve minimal Trend / Setup labels, or keep them null until typed structure
   evidence is retrievable?
6. Approve Key Trigger from active TradePlan entry only?
7. Confirm Support 1 remains null in PS-P5B?
8. Approve TradePlan stop as Major Support / Exit?
9. Confirm Target 2/3 remain null until a target ladder is separately approved?
10. Approve Next Action vocabulary: HOLD / ADD / REDUCE / EXIT / WATCH?
11. Should ADD require latest coherent EntryQualification QUALIFIED?
12. Should REDUCE be implemented from deterioration/gate evidence, or deferred?
13. Confirm ROTATE remains deferred?
14. Approve `portfolio-interpretation-v0` as methodology version?
15. Approve PS-P5B scope as implementation of the accepted subset only?
