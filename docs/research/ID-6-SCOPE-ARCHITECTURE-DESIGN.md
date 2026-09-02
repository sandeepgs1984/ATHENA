# ID-6 Scope & Architecture Design

**Date:** 2026-09-02
**Track:** Intraday Intelligence (ID)
**Milestone:** ID-6 - Discovery / scope and architecture freeze
**Status:** Ready for owner architecture review
**Recommendation:** GO WITH CONDITIONS

This report is documentation-only. It inspects the live repository state and
freezes the recommended ID-6 shape; it does not implement production behavior,
does not write `db/athena.db`, does not call a provider, and does not start
ID-7, EM-6, DarvaX, or any UI milestone.

## 1. Executive Summary

ID-6 should proceed toward Entry Qualification, but not as one large
"enter-now engine" milestone. The evidence foundation is mature enough to
define the next layer's contract because ID-0 through ID-5 now provide:

- explicit session state and completed-candle semantics;
- canonical-slot OR15/OR30;
- market/sector/stock relative strength;
- D1-only gap context;
- cumulative same-time RVOL with honest unavailable/stale-cutoff behavior;
- market-time point-in-time safety for candles, quotes, and snapshots;
- owner-approved ID-5B evidence that current-session Kite M5 can be
  market-time closed yet not provider-settled final.

The correct next step is therefore a scoped ID-6A implementation slice:
domain/state/reliability contracts for Entry Qualification. It should make
the live-M5 reliability policy explicit before any methodology thresholds are
tuned or any UI/TradePlan behavior is added.

## 2. Authoritative Starting State

ID-0 through ID-5 are owner-approved / closed. ID-5B's final accepted
classification is `CASE_B_CONTENT_CHANGES`: 704 of 705 eligible
closed-at-capture observations mapped stably by unique exact OHLCV content,
one eligible closed-at-capture row did not map to any settled OHLCV candidate,
18 forming-at-capture rows changed and remain excluded from CASE B evidence,
and zero off-grid provisional rows were observed in the frozen canary.

All current ID artifacts are analytical evidence only. There is no ID-specific
BUY/SELL score, no trade probability, no EntryQualification object, no
IntradayTradePlan, and no ID change to canonical scoring, confidence, risk,
DecisionEngine thresholds, or daily TradePlan construction.

Point-in-time support is market-time safe, not full knowledge-time /
bitemporal replay. EMR remains isolated by ADR-012, DarvaX remains isolated by
ADR-010, and no order-placement capability is permitted.

## 3. ID-5B CASE-B Implications

ID-5B does not justify either extreme. Current-session completed M5 cannot be
treated as unusable: almost every eligible closed observation was stable in
the canary. It also cannot be treated as settled-final: one closed-at-capture
row failed the exact-content settled comparison.

Production semantics for future decision-relevant intraday logic should
therefore distinguish four ideas:

- Market-time cutoff: the row is not future relative to `as_of`.
- Candle completion: `ts_open + timeframe <= as_of`.
- Provider finality: the provider's later settled representation may still
  differ.
- Knowledge-time replay: the database cannot reconstruct every provisional
  value ATHENA knew live after the provider/store has since changed.

The recommended policy is to treat current-session completed M5 as
`LIVE_PROVIDER_PROVISIONAL` evidence unless and until a future milestone
proves a narrower finality guarantee. Provisional evidence may contribute to
reversible state, but it must not create irreversible session-level rejection.

## 4. Current Runtime/Input Graph

The live production graph is `runtime.workflow.WorkflowStage`, not dormant
`domain.context.PipelineContext` / `IntelligenceModule` scaffolding.
`OwnerValidationPipeline._scan_eligible` builds a per-instrument DAG.

Current effective stage order is:

```text
indicators -> regime -> scoring -> risk -> confidence -> decision
          \                         /
           -> session -> relative_strength -> relative_volume -> intraday_analytics
```

`decision` currently does not consume `session`, `relative_strength`,
`relative_volume`, or `intraday_analytics`. ID-6 must use explicit
`depends_on` declarations; it must not rely on declaration order.

### Input Matrix

| Input | Producer/type | Stage/cadence | Uses current M5 | CASE B affected | Positive use | Negative use | Irreversible use |
|---|---|---|---:|---:|---|---|---|
| Daily Decision | `DecisionEngine` / `Decision` | `decision`; all scan cadences | No direct M5, but score may include VWAP/confluence | Indirect | Yes, as eligibility gate | Yes, for non-candidate states | Yes, for non-candidate/excluded only |
| Decision freshness | `Decision.trade_plan.valid_until`, newest decision read models | Derived from persisted decision | No | No | Yes | Yes | Yes when superseded/expired |
| Session phase | `SessionContextEngine` / `SessionContext.phase` | `session`; all scan cadences | No | No | Yes | Yes | Yes for closed/not-trading |
| Session data quality | `SessionContext.data_quality` | `session` | M5/M15 provenance | Yes for M5/M15 evidence quality | Yes if sufficient | Yes as unknown/not-ready | Not from provisional M5 alone |
| VWAP relation | `IntradayAnalyticsEngine` from VWAP result | `intraday_analytics`; all scan cadences | Yes | Yes | Yes, provisional | Yes, reversible only | No |
| 5m/15m trend/confluence | `ind_stage` + `IntradayTrendContext` | `indicators` / `intraday_analytics` | Yes | Yes | Yes, provisional | Yes, reversible only | No |
| OR15 | `OpeningRangeEngine` / `OpeningRangeEvidence` | `intraday_analytics` | Yes | Yes | Yes after formation complete, provisional | Yes, reversible only | No |
| OR30 | `OpeningRangeEngine` / `OpeningRangeEvidence` | `intraday_analytics` | Yes | Yes | Yes after formation complete, provisional | Yes, reversible only | No |
| GapContext | `GapEngine` / `GapContext` | `session` | No, D1-only | No | Yes if available | Yes if unavailable/adverse per later policy | Not alone without owner-approved method |
| RelativeStrengthContext | `RelativeStrengthEngine` | `relative_strength` | Yes for stock/index M5 | Yes | Yes, provisional | Yes, reversible only | No |
| RelativeVolumeContext | `RelativeVolumeEngine` | `relative_volume` | Yes numerator | Yes | Yes, provisional and freshness-aware | Yes, reversible only | No |
| Sector Health | `SectorHealthEngine` result | run-level then consumed by scoring/evidence/decision | D1/market context, not ID M5 | No direct ID-5B effect | Yes as structural context | Yes through existing gates | Existing Decision only |
| Regime/market context | `RegimeEngine` / `MarketHealthEngine` | `regime` | D1 + MarketSnapshot | Snapshot point-in-time, not M5 | Yes | Yes through existing gates | Existing Decision only |
| Latest quote | repository `get_latest_quote(..., as_of=...)` / `Quote` | `session`; persisted quote history | No OHLCV candle | No, but quote freshness matters | Observational price confirmation | Reversible stale/unknown | No |
| MarketSnapshot | repository `get_latest_snapshot_as_of` / `MarketSnapshot` | run-level snapshot | No | No | Yes via existing regime/health | Yes via existing gates | Existing Decision only |
| Liquidity/tradability | Volume MA, daily indicators, optional quote volume | `indicators`, persisted quotes | Mostly D1/quote | Not directly | Existing Decision/risk only | Existing Decision/risk only | Existing Decision only |

## 5. What ID-6 Should Be

ID-6 should be Entry Qualification in concept: a deterministic, explainable
layer that answers whether an existing daily/structural opportunity is
actionable now using accepted intraday evidence.

However, ID-6 should not jump directly to tuned thresholds, entries, stops,
targets, sizing, or live supervision. The next implementation milestone
should be ID-6A: freeze the domain contract, state machine, reliability
classification, provenance, and trace shape. The actual qualification engine
can follow only after owner review of this architecture.

## 6. Alternatives Considered

1. Treat completed current-session M5 as settled-final.
   Rejected. ID-5B found one eligible closed-at-capture content mismatch.

2. Treat all current-session M5 as unusable.
   Rejected. It would discard the primary information ID was created to use,
   despite 704/705 eligible closed observations remaining stable.

3. Keep ID-6 as generic "more evidence foundation."
   Rejected. The current gap is no longer raw evidence; it is the lack of a
   contract that turns evidence into actionable-now state.

4. Implement full EntryQualification immediately.
   Rejected. The CASE-B reliability policy, persistence identity, and state
   semantics need owner review before production behavior.

5. Proceed with EntryQualification in slices.
   Recommended. It preserves the payoff path while keeping methodology and
   provider-finality risks controlled.

## 7. Recommended Responsibility Boundary

ID-6 is:

- a post-Decision qualification layer;
- advisory-only;
- deterministic and replayable from injected inputs;
- explainability-owning at the point of qualification;
- reliability-aware for live M5 evidence;
- reversible unless a stable non-provisional gate makes the opportunity out
  of scope for the session.

ID-6 is not:

- entry-price generation;
- stop or target generation;
- position sizing;
- execution-quality scoring;
- live plan supervision;
- a replacement DecisionEngine;
- EMR ranking;
- DarvaX logic;
- broker/order behavior.

## 8. Proposed Domain Contract

Prefer the smallest new domain surface under `src/athena/intraday/`:

- `EntryQualificationState`
- `EntryQualificationReliability`
- `EntryQualificationReason`
- `EntryQualificationEvidenceRef`
- `EntryQualification`

Candidate fields:

- `qualification_id`
- `instrument_id`
- `session_date`
- `as_of`
- `decision_id`
- `decision_type`
- `state`
- `reliability`
- `evidence_refs`
- `reason_codes`
- `blocking_reasons`
- `stale_inputs`
- `unknown_inputs`
- `methodology_version`
- `config_snapshot_id` or equivalent run config reference when available
- `run_id`
- `cycle_id`
- `explanation`

Do not extend `SessionContext` to carry this. SessionContext describes the
session and timeframe provenance; EntryQualification is a consumer-level
judgement. Do not extend `Decision` in ID-6A unless owner specifically wants
the current daily Decision object to carry intraday state; separate persistence
keeps canonical DecisionEngine methodology unchanged.

## 9. Proposed State Machine

Recommended states:

- `OUT_OF_SCOPE`: no current eligible daily Decision, session not applicable,
  or the candidate is superseded by a non-candidate daily Decision.
- `UNKNOWN`: required inputs are missing, stale, or contradictory enough that
  no honest qualification state can be emitted.
- `NOT_YET`: the setup is not currently actionable but may become actionable
  later in the same session.
- `QUALIFIED_PROVISIONAL`: actionable-now conditions are met using at least
  one current-session M5-derived input whose provider finality is provisional.
- `QUALIFIED_CONFIRMED`: actionable-now conditions are met without relying on
  unconfirmed current-session M5 inputs, or after an owner-approved
  confirmation policy has been satisfied.
- `DISQUALIFIED_FOR_SESSION`: stable, non-provisional facts make the setup
  invalid for the rest of the session.
- `EXPIRED`: the session phase or bound daily Decision/TradePlan validity
  naturally ended the qualification.

Semantics:

- `NOT_YET` is reversible.
- `QUALIFIED_PROVISIONAL` is reversible.
- `QUALIFIED_CONFIRMED` is still reversible if later live evidence degrades.
- `DISQUALIFIED_FOR_SESSION` is terminal for the session, but only from stable
  non-provisional facts or explicit owner-approved rules.
- Stale evidence transitions to `UNKNOWN` or `NOT_YET`, not terminal
  disqualification.
- Later completed-M5 reinterpretation can downgrade or upgrade reversible
  states, with a new observation and reason code.
- Provisional evidence can create `QUALIFIED_PROVISIONAL`.
- Provisional evidence cannot create `DISQUALIFIED_FOR_SESSION`.
- Qualification naturally expires when the session is closed/not applicable or
  the bound daily Decision/TradePlan is no longer current.

## 10. Daily Decision Relationship

EntryQualification should bind to one specific persisted `Decision` by
`decision_id`, `run_id`, `cycle_id`, `decision_type`, `ts`, and preferably the
configuration/run provenance available through that decision's originating
run.

Candidate funnel:

- `TRADE`: eligible for qualification; existing `TradePlan` is present but
  should not be modified by ID-6.
- `WATCH`: eligible for observation/qualification, but any future entry plan
  must distinguish that the canonical Decision is not already a TRADE.
- `NO_TRADE`, `INSUFFICIENT_DATA`, `DATA_VALIDATION_FAILED`, `MARKET_CLOSED`,
  and other non-candidate states: out of scope unless a future owner-approved
  methodology says otherwise.

A later same-session daily Decision supersedes prior qualifications for the
same instrument. Existing decision-list scoping can be reused for candidate
selection, especially FAST revalidation, but ID-6 must dedupe by latest
decision per instrument and must never revive an earlier WATCH/TRADE after a
newer non-candidate Decision.

## 11. Live-M5 Reliability Policy

| Evidence family | Source/timeframe | Provisional sensitivity | Display | Qualification-positive | Qualification-negative | Confirmation | Fallback |
|---|---|---|---|---|---|---|---|
| Session phase | Calendar/session config | None | Yes | Yes | Yes | No | `OUT_OF_SCOPE`/`EXPIRED` |
| Session M5 quality | M5/M15 provenance | High for live M5 | Yes | Indirect | Reversible only | Yes if used to assert actionability | `UNKNOWN` |
| VWAP | Current-session M5 | High | Yes | Provisional | Reversible only | Required for confirmed state | `UNKNOWN`/`NOT_YET` |
| 5m trend | Current/recent M5 | High | Yes | Provisional | Reversible only | Required for confirmed state | `UNKNOWN`/`NOT_YET` |
| 15m trend | Current/recent M15 | Medium/high | Yes | Provisional | Reversible only | Required for confirmed state | `UNKNOWN`/`NOT_YET` |
| OR15/OR30 | Current-session M5 | High | Yes when formation known | Provisional when complete | Reversible only | Required for confirmed state | `UNKNOWN` before complete/incomplete |
| Relative Strength | Stock/index current M5 | High | Yes | Provisional | Reversible only | Required for confirmed state | `UNKNOWN` |
| RVOL | Current M5 volume + settled baseline | High for numerator | Yes | Provisional and freshness-aware | Reversible only | Required for confirmed state | `UNKNOWN`/stale |
| GapContext | Current/previous D1 | Low | Yes | Yes | Reversible unless later methodology says terminal | No live-M5 confirmation | `UNKNOWN` |
| Daily Decision | Persisted Decision | Low, but indirect score exposure exists | Yes | Eligibility gate | Out-of-scope gate | No | `OUT_OF_SCOPE` |
| Latest quote | Quote history | Not M5-settlement sensitive | Yes | Observational only until methodology approved | Reversible stale/unknown | Freshness policy required | `UNKNOWN` |

This table is proposed policy, not implemented configuration.

## 12. UNKNOWN / Missing / Stale Semantics

`UNKNOWN` means ATHENA cannot honestly evaluate the qualification state. It is
not equivalent to bearish, failed, matching, or no event.

Missing required evidence should produce `UNKNOWN` unless the missingness
itself is an accepted stable out-of-scope condition. Stale provisional evidence
should degrade to `UNKNOWN` or `NOT_YET`; it must not produce
`DISQUALIFIED_FOR_SESSION`. RVOL deserves special handling because it can be
available at a valid earlier `comparison_cutoff_ts` even when real time has
moved beyond that cutoff. ID-6 must compare `as_of` to each evidence artifact's
own cutoff/provenance and record freshness honestly.

## 13. Pipeline Placement

Logical placement: add a future `entry_qualification` `WorkflowStage` after
`decision` and `intraday_analytics`, with explicit dependencies:

```text
depends_on=("decision", "session", "intraday_analytics")
```

If the implementation consumes `relative_strength`, `relative_volume`, or
`gap_context` directly rather than through `intraday_signal_set`, declare those
dependencies too. Prefer consuming `intraday_signal_set` to avoid duplicating
the graph.

The stage should run in the existing PREMARKET/REFRESH/FAST/CLOSING/Revalidate
paths with session-aware outputs:

- PREMARKET before regular session: likely `OUT_OF_SCOPE` or `UNKNOWN`, not
  fabricated actionability.
- REFRESH/FAST during market: primary intended cadence.
- CLOSING/closed: `EXPIRED` or non-actionable.
- Single-symbol Revalidate: same stage and same contracts, scoped to the
  requested symbols.

No new scheduler, no second pipeline framework, and no `PipelineContext`
resurrection are required. Cycle locking/concurrency assumptions stay the same
if ID-6 remains inside the existing `OwnerValidationPipeline` run.

## 14. Persistence & Explainability

Persistence is recommended, but in slices:

1. ID-6A freezes the domain object and trace contract.
2. ID-6C adds append-only persistence plus latest-state projection if owner
   approves the contract.

Derived-at-read alone is not enough for the intended query "show me currently
qualified intraday opportunities" because the answer must remain auditable
against what ATHENA knew at that cycle. ADR-005 requires the qualification
itself to own its explanation at creation time.

Suggested persistence model:

- append-only `entry_qualifications` observation table;
- optional latest-state query by `(instrument_id, session_date)` using the
  newest observation;
- foreign/provenance references to `decision_id`, `run_id`, `cycle_id`;
- JSON evidence refs for `session_context`, `intraday_signal_set`, OR windows,
  RS, gap, RVOL, quote/snapshot references where available;
- explicit `state`, `reliability`, reason codes, unknown/stale inputs, and
  explanation;
- methodology/config version fields;
- no mutation of `decisions` or `decision_traces` required in the first
  persistence slice.

## 15. Replay / Determinism Contract

The engine should be pure: all inputs injected, no provider access, no
repository access, no wall-clock reads, no randomness, `Decimal` math only, and
timezone-aware timestamps.

Replay limitation: current repository improvements guarantee market-time
cutoff safety for candles, quotes, and snapshots, but not knowledge-time
reconstruction of provisional values observed live before provider settlement.
Historical settled M5 can prove feasibility and distribution, but it cannot by
itself prove exactly what ATHENA would have known during a live provisional
session.

## 16. Validation Methodology

Do not invent thresholds and call the engine complete. Use this sequence:

1. Contract tests for state transitions, unknown/stale behavior, Decision
   binding, and provisional-vs-confirmed reliability.
2. Historical/replay feasibility using settled M5, explicitly labeled as
   feasibility rather than live-knowledge truth.
3. Distribution/base-rate measurement of candidate evidence combinations.
4. Threshold candidate analysis only where the owner authorizes thresholds
   such as RVOL bands, ORB extension, VWAP distance, or RS magnitude.
5. Chronological validation before any tuned rule is promoted.
6. Shadow/live observation because CASE B prevents pretending settled history
   is identical to live knowledge.
7. Owner promotion gate before ID output becomes a production-facing action
   surface.

## 17. Performance / Scale Impact

The recommended architecture composes already-produced artifacts. ID-6A should
add no repository reads. A future engine stage should consume `Decision`,
`SessionContext`, and `IntradaySignalSet` from `WorkflowContext` and perform
small in-memory rule evaluation per instrument.

If persistence is approved, expected extra work is one append-only write per
candidate observation, plus a latest-state index/query. FAST impact should be
bounded by the existing decision-list scope. Single-symbol Revalidate should
add trivial in-memory cost and at most one persistence write. Full-universe
REFRESH cost is proportional to existing included instruments, with no new
N-by-M market/sector refetch if the stage consumes existing contexts.

## 18. ADR Impact

No ADR is required for the discovery document itself.

An ADR is not required if ID-6 stays inside the existing `intraday` package,
uses `WorkflowStage`, adds an ID-owned domain object/persistence table, and
does not modify frozen DecisionEngine/scoring/risk/provider contracts.

An ADR or separate owner architecture decision would be required if ID-6:

- changes the ATHENA-002 module map;
- adds provider bid/ask/depth or execution-quality interfaces;
- changes Decision/TradePlan canonical contracts rather than adding a separate
  ID artifact;
- introduces knowledge-time/bitemporal storage guarantees;
- alters scoring, confidence, risk, DecisionEngine, or order/broker behavior.

## 19. Explicitly Deferred Work

- Entry price generation.
- Stop loss and target methodology.
- Position sizing and capital allocation.
- Execution-quality scoring from bid/ask/depth.
- UI/dashboard presentation.
- Live plan supervision.
- ID-7 and later milestones.
- EM-6, EMR integration, DarvaX integration.
- Current-session candle normalization, rounding, resampling, repair, or
  synthetic reconstruction.
- Rolling RVOL baseline cap and corporate-action volume adjustment.
- Knowledge-time/bitemporal replay storage.
- Any trade probability model.

## 20. Risks / Open Questions

- CASE B was narrow but real; over-trusting live M5 would be unsafe, while
  discarding it would make ID toothless.
- WATCH-vs-TRADE treatment needs owner confirmation because WATCH may be a
  strong intraday candidate but lacks the invariant that a TRADE carries a
  TradePlan.
- `QUALIFIED_CONFIRMED` requires a confirmation definition. This report
  recommends the state name and semantics, not a tuned confirmation rule.
- Persistence schema should be reviewed before implementation because it
  affects long-term audit and latest-state queries.
- True execution quality remains unsupported by current `Quote` and
  `MarketDataProvider` contracts.

## 21. Proposed ID-6 Implementation Slices

| Slice | Responsibility | Inputs/outputs | Likely files | Tests | Exit criteria |
|---|---|---|---|---|---|
| ID-6A | Domain/state/reliability contract | Proposed `EntryQualification*` types only | `src/athena/intraday/entry_qualification_models.py`, docs | Unit contract tests | Frozen states, reliability, reason-code semantics owner-reviewable |
| ID-6B | Pure deterministic qualification engine skeleton | Inputs: `Decision`, `SessionContext`, `IntradaySignalSet`; output: `EntryQualification` | `src/athena/intraday/entry_qualification_engine.py` | Unit tests for state transitions and unknown/stale behavior | No thresholds beyond accepted zero-threshold categories; no I/O |
| ID-6C | Persistence and explainability trace | Append-only observations + latest query | `data/store/schema.py`, repository serialization/repository tests | Repository contract tests, migration tests | Auditable current-state query without mutating `Decision` |
| ID-6D | Workflow integration | `entry_qualification` stage after `decision` + `intraday_analytics` | `ops/owner_validation.py` | Stage order, no scoring/decision perturbation, FAST/Revalidate tests | Existing Decision output unchanged; ID output captured separately |
| ID-6E | Replay/shadow validation plan | Feasibility + live/shadow evidence reports | `docs/research/`, possibly analysis scripts | Deterministic replay checks | Owner-reviewed promotion evidence; limitations labeled |

Every slice stops for owner approval before the next begins.

## 22. Recommendation

GO WITH CONDITIONS.

Conditions:

- Owner approves EntryQualification as the conceptual ID-6 direction.
- Owner approves the provisional-live-M5 policy before any production
  qualification engine relies on current-session M5.
- ID-6 implementation begins with ID-6A contract/state/reliability only.
- No thresholds, entry plan, stop/target/sizing, UI, EMR, DarvaX, or order
  behavior are introduced in ID-6A.

## Milestone Review Summary

**Name:** ID-6 Discovery / Scope & Architecture Freeze

**Objective:** Determine what ID-6 should be from the live architecture and
ID-0 through ID-5 evidence, especially ID-5B `CASE_B_CONTENT_CHANGES`.

**Scope completed:** Inspected current docs, governing architecture, ADRs,
session/intraday domain and engines, live workflow graph, Decision/TradePlan
contracts, persistence schema, provider quote capabilities, EMR isolation
handoff, and ID-5B final evidence. Produced this design report.

**Files created:** `docs/research/ID-6-SCOPE-ARCHITECTURE-DESIGN.md`.

**Files modified:** `docs/MILESTONES.md`,
`docs/ATHENA-ID-TRACK-HANDOFF.md`, `ATHENA_BRIEFING.md`,
`IMPLEMENTATION_SUMMARY.md`.

**Public APIs added:** None.

**Tests added:** None.

**Test results:** No pytest run; this is documentation-only. `git diff
--check` is expected before final handoff.

**Coverage summary:** Not applicable; no production code changed.

**Architecture compliance:** Preserves ATHENA-002, ADR-003 Amendment 1, and
ADR-005. No provider, scoring, confidence, risk, DecisionEngine, TradePlan,
EMR, DarvaX, or order behavior changed.

**ADR compliance:** No ADR required for this discovery milestone. Future
implementation needs an ADR only if it changes provider interfaces, Decision
contracts, module boundaries, or knowledge-time storage guarantees.

**Risks discovered:** Live M5 finality remains provisional; WATCH-vs-TRADE
funnel policy and confirmed-qualification methodology need owner decisions.

**Technical debt introduced:** None.

**Suggested improvements:** Implement ID-6A first as a small, reviewable
domain/state/reliability contract before any engine or persistence work.

**Remaining work:** Owner architecture review; then, if approved, ID-6A only.
Do not start ID-7.

**Commit message:**

```text
docs(review): freeze ID-6 entry qualification architecture

- Add the ID-6 discovery report to define Entry Qualification scope and
  live-M5 provisional semantics after ID-5B CASE B.
- Record ID-6 as ready for owner architecture review without implementing
  production behavior.
- Preserve EMR, DarvaX, scoring, Decision, TradePlan, provider, and order
  boundaries per ATHENA-002, ADR-003, ADR-005, and ADR-012.
```

**Ready for review:** Yes.
