# ID-6B Entry Qualification Methodology / Engine Design

**Date:** 2026-09-02
**Track:** Intraday Intelligence
**Milestone:** ID-6B.0 - Entry Qualification methodology / engine design
**Status:** Discovery complete; ready for owner methodology review
**Recommendation:** GO WITH CONDITIONS

This report is documentation and read-only analysis only. It does not implement
the Entry Qualification engine, does not add persistence or migrations, does
not wire workflow, does not create thresholds, does not call a provider, does
not write `db/athena.db`, and does not touch EMR, DarvaX, ID-6C, ID-6D,
ID-6E, or ID-7.

## 1. Executive Summary

ID-6B should proceed, but only after the owner approves a deliberately small
v0 methodology. The repository has enough architecture to build a pure
post-Decision Entry Qualification engine: ID-6A defines the immutable output
contract, ADR-013 freezes the state/finality/confirmation separation, and
ID-1 through ID-5 provide session, VWAP/trend, OR, RS, gap, RVOL, and
point-in-time market-time safety.

The repository does not yet justify a tuned scoring formula, weighted
qualification score, hard all-signal gate, or terminal intraday rejection
policy. Current ID artifacts are mostly descriptive categorical contexts, not
owner-approved qualification gates. The current database has abundant
WATCH/TRADE Decisions and M5 candles, but no persisted `IntradaySignalSet`
history and only one realized trade outcome, so ID-6B.0 cannot honestly claim
outcome-optimized rules.

Recommended path: implement ID-6B as a pure deterministic engine only after
owner review of this report. The v0 policy should use canonical WATCH/TRADE
Decisions as structural candidates, require fresh/same-session evidence to
avoid false confidence, allow provisional live-M5 evidence to support
`QUALIFIED`, emit reversible `NOT_YET` for unmet actionability evidence, emit
honest `UNKNOWN` for missing/stale/unassessable evidence, and avoid
`DISQUALIFIED_FOR_SESSION` until a genuinely irreversible, non-provisional
session rule is separately approved.

## 2. ID-6A Accepted Starting State

ID-6A is owner-approved / closed as of 2026-09-02. The accepted contract is
`src/athena/intraday/entry_qualification_models.py`:

- `EntryQualificationState`: `OUT_OF_SCOPE`, `UNKNOWN`, `NOT_YET`,
  `QUALIFIED`, `DISQUALIFIED_FOR_SESSION`, `EXPIRED`.
- `EntryEvidenceFinality`: `UNKNOWN_PROVENANCE`,
  `LIVE_M5_PROVISIONAL`, `NO_DECISIVE_PROVISIONAL_M5_DEPENDENCY`.
- `EntryQualificationConfirmation`: `UNKNOWN`, `NOT_EVALUATED`,
  `NOT_CONFIRMED`, `CONFIRMED_BY_POLICY`.
- `EntryQualification`: frozen, advisory-only, bound to one canonical
  `Decision`, with `run_id`, `cycle_id`, `decision_id`, `decision_type`,
  `as_of`, `session_date`, reason codes, evidence refs, methodology/config
  provenance, and an ADR-005 explanation.

No engine, persistence, workflow stage, threshold, UI, provider behavior, DB
write path, Entry/IntradayTradePlan, EMR, DarvaX, or order behavior exists.

## 3. Exact Question ID-6B Answers

Given an already-produced canonical `WATCH` or `TRADE` `Decision`, what
deterministic evidence-supported method should ATHENA use to conclude whether
that candidate is actionable now?

ID-6B does not decide what is worth watching from scratch. It evaluates one
bound canonical Decision at one explicit `as_of` using explicit immutable
intraday evidence and provenance.

## 4. Current Evidence Graph

The live path is:

```text
D1 candles + snapshots -> regime / market / sector context
D1 indicators + current-session M5/M15 -> indicators, VWAP, confluence
scoring + confidence + risk -> canonical Decision
session + ID artifacts -> IntradaySignalSet
Decision + SessionContext + IntradaySignalSet -> future EntryQualification
```

Important overlap:

```text
current-session M5 -> VWAP/confluence -> ScoringEngine -> Decision
current-session M5 -> IntradaySignalSet -> EntryQualification
```

Thus Entry Qualification sees direct live-M5 provisionality through
`IntradaySignalSet` and indirect live-M5 exposure through the bound
`Decision`.

## 5. Eligibility Model

Recommended structural eligibility:

- Eligible decision types: `WATCH` and `TRADE`.
- Out of scope: `NO_TRADE`, `INSUFFICIENT_DATA`,
  `DATA_VALIDATION_FAILED`, `MARKET_CLOSED`, and other non-candidate Decision
  types.
- Required identity alignment: `Decision.instrument_id`,
  `SessionContext.instrument_id`, and `IntradaySignalSet.instrument_id` must
  match; `session_date` must match the evaluated session.
- Required freshness: the Decision must be the latest known Decision for that
  instrument supplied by the caller/future adapter. Superseded observations
  should be `EXPIRED`, not silently re-evaluated as current.
- Required lifecycle: Entry Qualification is meaningful only inside a trading
  session lifecycle. Non-trading session or after-close observations cannot be
  live actionability.

Do not use weak intraday momentum, below-VWAP price, RS underperformance, or
RVOL weakness as structural `OUT_OF_SCOPE`. Those are readiness observations,
not eligibility.

## 6. Readiness Model

Readiness should answer whether current intraday evidence supports
actionability now. Recommended v0 policy shape:

- Mandatory for any non-`UNKNOWN` readiness: same-session `SessionContext`,
  same-session `IntradaySignalSet`, and `SessionDataQualityStatus.SUFFICIENT`.
- Mandatory positive evidence candidates: price above VWAP and bullish
  5m/15m trend. These are the only two intraday features already known to
  overlap the current scoring path, so they are useful but double-counting
  sensitive.
- Confirmation-support candidates: OR relation/event, stock relative strength,
  RVOL participation, and gap context. These should begin as contextual or
  policy-confirmation inputs, not automatic hard gates.
- Sector Health: structural context already enters canonical scoring; treat it
  as an inherited Decision context unless a later policy approves using it as
  an Entry Qualification veto.

No numeric readiness score is recommended for v0. If owner wants immediate
QUALIFIED output in ID-6B, approve a categorical rule explicitly rather than
inventing one in code.

## 7. Confirmation Model

`CONFIRMED_BY_POLICY` must mean "the owner-approved Entry Qualification
confirmation policy passed." It must not mean provider-settled, historically
immutable, multi-signal confirmed by default, or free of live-M5
provisionality.

Recommended v0 confirmation alternatives:

- Conservative: set confirmation to `NOT_EVALUATED` or `NOT_CONFIRMED` until
  a replay/shadow phase proves a confirmation policy.
- Practical v0: `CONFIRMED_BY_POLICY` requires fresh same-session data,
  above-VWAP relation, bullish 5m/15m trend, and at least one non-overlapping
  participation/context support from RS or RVOL. OR/GAP remain explanatory
  unless separately approved.

The practical v0 alternative is implementable, but it is a methodology choice
for owner approval, not a consequence of existing contracts.

## 8. Terminal-Disqualification Analysis

Recommended initial policy: do not emit `DISQUALIFIED_FOR_SESSION` in ID-6B
v0 except for a future owner-approved terminal rule whose decisive cause is
known not to depend solely on provider-provisional live M5.

Reasons:

- Most candidate failures are reversible intraday states: below VWAP, mixed
  trend, no OR breakout, low RVOL, RS underperformance.
- ID-5B proved current-session completed M5 can differ from provider-settled
  historical representation.
- Current Decision provenance cannot always prove whether a downgrade was
  caused solely by provisional M5 through VWAP/confluence scoring.

Use `NOT_YET` for reversible non-actionability and `UNKNOWN` for missing,
stale, or unassessable evidence.

## 9. Artifact Methodology Matrix

| Artifact | Exact fields | Producer | Timeframe | Semantics | Freshness | Missing/UNKNOWN | M5 sensitivity | PIT/replay | Direct/indirect overlap | Candidate role | Evidence | Double-count risk | Recommendation |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Decision | `decision_id`, `decision_type`, `ts`, `instrument_id`, `run_id`, `cycle_id`, `trade_plan` | `DecisionEngine` | scan `as_of` | canonical structural candidate | caller must provide latest/current | non-candidate -> `OUT_OF_SCOPE`; superseded -> `EXPIRED` | indirect through scoring VWAP/confluence | persisted, market-time | overlaps with VWAP/trend | structural eligibility | owner-approved canonical Decision contract | high if intraday supports are recounted as independent score | required input |
| SessionContext | `phase`, `data_quality`, M5/M15 provenance, quote timestamp | `SessionContextEngine` | current session | session lifecycle and data quality | `as_of` explicit | `UNKNOWN` unless stable lifecycle out-of-scope | M5/M15 provenance | market-time replay, no knowledge-time | direct input only | required validity context | ID-1 accepted | low | mandatory |
| VWAP | `relation`, `deviation_pct` | `IntradayAnalyticsEngine` from `IndicatorResult` | current-session M5 | price vs session VWAP | tied to session data | unavailable -> `UNKNOWN` if mandatory | direct live M5 | settled replay differs from live possible | already affects scoring | positive readiness candidate | existing scoring use proves relevance | high with Decision technical score | v0 mandatory only if owner approves |
| Trend | `five_min.bullish`, `fifteen_min.bullish`, `trend_label` | `IntradayAnalyticsEngine` from confluence | M5/M15 | short intraday directional structure | tied to M5/M15 data | `UNKNOWN` if either leg unavailable | direct live M5/M15 | settled replay limitation | already affects scoring | positive readiness candidate | existing confluence scoring use proves relevance | high with Decision trend score | v0 mandatory only if owner approves |
| OR15 | `formation.status`, `relation`, `breakout_event`, extensions | `OpeningRangeEngine` | M5 first 15 minutes | opening range measurement/event | complete only after elapsed expected bars | forming/incomplete/not available -> not negative | direct live M5 | market-time replay, no knowledge-time | overlaps with trend/VWAP price action | contextual / confirmation support | ID-3 accepted as evidence only | medium-high | not a hard v0 gate without approval |
| OR30 | same as OR15 | `OpeningRangeEngine` | M5 first 30 minutes | wider opening range measurement/event | complete later than OR15 | forming/incomplete/not available -> not negative | direct live M5 | market-time replay, no knowledge-time | overlaps with OR15/trend/VWAP | contextual / confirmation support | ID-3.1 fixed canonical slots | medium-high | prefer context until distribution analysis |
| RelativeStrength | stock/sector/market returns and relations | `RelativeStrengthEngine` | current-session M5 common cutoff | comparative performance | explicit common cutoff | unavailable dimensions -> ignore optional or `UNKNOWN` if mandatory | direct live M5 | settled replay limitation | complements Decision sector context | participation/support | ID-4/4.1 accepted | medium with sector health | support, not hard gate initially |
| GapContext | `gap_pct`, `direction`, availability | `GapEngine` | D1 previous close/current open | session-open transition | fixed once D1 data exists | unavailable -> context missing | no M5 dependency | replay-safe with D1 | no direct scoring overlap | context/filter later | ID-5C accepted | low-medium with momentum narratives | contextual only in v0 |
| RelativeVolume | `rvol_ratio`, `relation`, cutoff, baseline count | `RelativeVolumeEngine` | cumulative same-time M5 vs historical M5 | participation vs baseline | explicit comparison cutoff | unavailable/stale -> `UNKNOWN` if mandatory; ignore if optional | numerator live M5 | settled replay limitation | overlaps with volume breakout ideas | confirmation support | ID-5D/5D.1 accepted | medium with OR breakout volume | support, not sole gate |
| Sector Health | categorical sector result/score context | `SectorHealthEngine` + scoring | D1/market context | sector quality | run-level current | missing handled by scoring as unknown | no ID current M5 | persisted indirectly only | already affects Decision | inherited structural context | owner-approved scoring path | high with Decision sector quality | do not re-gate v0 |
| Quote | `latest_quote_ts`, LTP via quote store | repository/session | quote ticks | freshness/observed price | as_of bounded by ID-5F | stale/unavailable -> `UNKNOWN` if required | not M5 settlement | market-time safe, not knowledge-time | supports session only | freshness input later | quote PIT fixed in ID-5F | low | do not use for entry price in ID-6B |

## 10. Double-Counting / Correlation Analysis

Major overlap risks:

- Decision already includes VWAP and confluence bonuses; using VWAP/trend again
  as Entry Qualification gates is acceptable only if ID treats them as
  temporal readiness, not as additional conviction points.
- VWAP, 5m trend, 15m trend, OR breakout/relation, and gap-follow-through all
  describe price location or movement. They should not be added as independent
  votes in a score.
- OR15 and OR30 overlap heavily. Running both as separate hard gates would
  overstate one concept: opening range structure.
- RS and Sector Health are complementary but not independent. Sector Health is
  inherited through Decision; stock RS can answer whether this stock is
  participating relative to that context.
- RVOL and OR breakout volume/extension would overlap if future rules add
  volume-based breakout strength.

Recommended mitigation: no additive qualification score in v0. Use a layered
state machine and explanations that name evidence families rather than sum
them.

## 11. IntradaySignalSet Contract Audit

`IntradaySignalSet` currently contains:

- `instrument_id`, `session_date`, `as_of`.
- `vwap`: categorical price-vs-VWAP evidence plus `deviation_pct`.
- `trend`: 5m and 15m SMA-direction evidence plus aggregate
  `BULLISH`/`BEARISH`/`MIXED`/`UNKNOWN`.
- `or15`, `or30`: formation, relation, breakout event, extension and
  returned-inside-range fields.
- `relative_strength`: stock-vs-sector/market and sector-vs-market
  comparative return context.
- `gap`: previous-session-close to current-session-open context.
- `relative_volume`: same-time cumulative RVOL context.
- `data_quality`: copied from `SessionContext`.
- `explanation`: ADR-005 owner-facing summary.

Field nature:

- VWAP/trend/OR/RS/RVOL are derived from current-session M5 and therefore
  live-M5 provisional for same-day qualification.
- Gap is D1-only and not M5-sensitive.
- Data quality and timestamps are context/provenance, not signal strength.
- The object is a value object today, not a persisted artifact with a stable
  `intraday_signal_set_id`.

## 12. Direct Live-M5 Provisionality

ID-5B closed as `CASE_B_CONTENT_CHANGES`: one closed-at-capture M5 row failed
to map by exact settled OHLCV content to the later provider-settled
representation. Therefore current-session completed M5 is market-time safe
but not provider-final.

Direct policy:

- `QUALIFIED` may be emitted from live-M5-provisional evidence if the
  owner-approved method says current readiness is satisfied.
- `NOT_YET` may be emitted from live-M5-provisional evidence because it is
  reversible.
- `UNKNOWN` should be emitted when provenance or required evidence is
  unassessable.
- `DISQUALIFIED_FOR_SESSION` must not be emitted when its decisive cause is
  solely live-M5-provisional.

## 13. Indirect Decision Provisionality

Current capability: **C - insufficient for stable first-class provenance**.

Why:

- `ScoringEngine` accepts `vwap` and `confluence` and can move `trend` and
  `technical_structure`.
- `DecisionEngine` consumes only scoring/confidence/risk/evidence/regime
  objects directly; it does not receive first-class intraday provenance.
- `DecisionTrace` persists stage summaries and score explanation text, but
  not a typed "this Decision depended decisively on live M5" field.
- `score_ref`, `confidence_ref`, and `risk_ref` are plain references; there
  are no scoring/confidence/risk tables preserving full typed provenance.

Smallest conservative behavior: if the future engine cannot prove the bound
Decision's decisive eligibility/downgrade is free of live-M5 influence, mark
finality as `UNKNOWN_PROVENANCE` or `LIVE_M5_PROVISIONAL` and prohibit only
irreversible rejection. Positive and reversible states can still proceed.

## 14. WATCH vs TRADE Treatment

Recommendation: same qualification evidence, different interpretation.

- `TRADE` carries canonical trade intent and a daily `TradePlan`; ID-6B may
  qualify the intraday actionability of that existing TRADE candidate.
- `WATCH` is eligible, but `QUALIFIED` must not promote it to
  `DecisionType.TRADE` and must not create an entry plan.
- Do not invent stricter WATCH thresholds. If the same intraday readiness
  policy passes, preserve `decision_type=WATCH` in the output and let future
  ID-7/ID-8 decide plan/risk handling.

## 15. Session-Phase Semantics

Use only existing `SessionPhase`:

- `NOT_A_TRADING_SESSION`: `OUT_OF_SCOPE` for live intraday actionability.
- `PRE_OPEN`: usually `NOT_YET` if the candidate is structurally eligible and
  the session is pending; `UNKNOWN` if required pre-open context itself is
  unavailable.
- `REGULAR`: normal evaluation window.
- `CLOSED`: `EXPIRED` for same-session live actionability after the session
  lifecycle ends.

Do not invent additional clock windows such as late-session cutoffs or opening
cooldowns in ID-6B.0.

## 16. Missing / Stale / UNKNOWN Semantics

Policy:

- Missing `Decision`: cannot produce Entry Qualification.
- Non-WATCH/TRADE Decision: `OUT_OF_SCOPE`.
- Superseded Decision: `EXPIRED`.
- Missing `SessionContext` or `IntradaySignalSet`: `UNKNOWN`.
- Instrument/session/as_of mismatch: `UNKNOWN` unless the bound Decision is
  clearly expired.
- `SessionDataQualityStatus` other than `SUFFICIENT`: `UNKNOWN` for any rule
  that requires affected intraday evidence.
- VWAP unavailable or trend unknown: `UNKNOWN` if owner approves them as v0
  mandatory; otherwise omit them from optional support.
- OR forming/incomplete/not available: do not treat as negative evidence.
- RS/RVOL unavailable: do not substitute with matching/baseline; either
  `UNKNOWN` if mandatory or ignored as optional context.
- Gap unavailable: contextual missingness, not bearish evidence.
- Unknown indirect Decision provenance: prohibit irreversible rejection;
  allow positive/reversible evaluation with truthful finality.

## 17. Existing Threshold Inventory

Existing thresholds and categorical boundaries:

- `config/decision.json`: trade composite 60, watch composite 50, minimum
  confidence 50, maximum risk 50, evidence completeness 0.5, market floor 40,
  ATR stop multiple 1.5, ATR target multiple 3.0, validity 6 hours.
- `config/scoring.json`: component weights, label point map, RSI 40/60, ADX
  15/25 with max 10 bonus, liquidity volume MA 500000 and 0.5 floor ratio,
  SMA/MACD points, VWAP deviation cap 1.5% with max 10 bonus, confluence
  M5 SMA(9), M15 SMA(5), max 10 bonus.
- `config/sector_health.json`: MA 10/30, breadth 0.60/0.40, momentum period 10
  with 3.0%, volatility window 20 with 1.0/2.5%.
- `config/market.nse.json`: pre-open 09:00-09:08, regular open 09:15, close
  15:30.
- ID artifact categories: VWAP sign at 0, trend agreement/disagreement,
  OR boundary relation/event, RS differential sign at 0, RVOL ratio sign at
  1.0, gap sign at 0.

Owner-approved upstream thresholds define upstream artifacts and canonical
Decision behavior only. Reusing any as Entry Qualification gates is a new
methodology decision unless explicitly approved.

## 18. Historical-Data Availability

Read-only SQLite inspection found:

- `decisions`: 96,985 `TRADE`, 83,641 `WATCH`, 33,726 `NO_TRADE`.
- Recent candidate volume is high: examples include 4,691 WATCH on
  2026-09-01, 4,216 WATCH on 2026-08-31, and multiple recent sessions with
  thousands of TRADE decisions.
- `candles`: 1,136,324 M5 rows across 538 instruments from 2026-07-23 through
  2026-09-02; 275,260 M15 rows across 538 instruments; 1,400,070 D1 rows
  across 2,204 instruments.
- Runs: 1,839 total, with `REFRESH`, `FAST`, `PREMARKET`, and `CLOSING`
  triggers represented.
- No `entry_qualification` table exists, as expected.

This supports deterministic replay/distribution analysis over settled data,
but not direct historical lookup of prior `IntradaySignalSet` states.

## 19. Distribution / Base-Rate Findings

Feasible now:

- Count candidate Decision prevalence by type/date.
- Rerun deterministic session/intraday artifact generation over settled M5
  for selected dates/checkpoints.
- Measure availability and combinations of VWAP/trend/OR/RS/RVOL states from
  replayed artifacts.
- Measure how often WATCH/TRADE candidates have missing or unavailable
  intraday evidence in settled replay.

Not feasible from existing persisted rows alone:

- Historical transition sequences of `IntradaySignalSet` as observed live.
- Knowledge-time provisional-vs-settled differences across the whole universe.
- Outcome-conditioned qualification lift, because realized labels are too
  sparse.

Initial base-rate caution: WATCH/TRADE Decisions are common in the current
book. A permissive qualification rule may be too ubiquitous; an all-artifact
hard gate may be too rare or delayed. ID-6B implementation should include a
distribution harness before promoting any rule to owner-facing production.

## 20. Outcome / Label Availability

The domain has `TradeOutcome`, `DecisionJournalEntry`, and a
`trade_outcomes` table, but the production database currently contains only
one trade outcome and one journal row. That is not enough to evaluate ID
methodology.

EMR has extensive MFE/MAE/label utilities and datasets, but those are governed
by ADR-012 and EMR methodology. ID may audit shared low-level deterministic
utilities later, but must not import EMR scoring semantics, explosive-move
labels, or final-test leakage into ID.

ID needs a neutral future evaluation harness for questions such as +1%/+1.5%,
MAE first, time-to-target, and setup persistence. The 1-1.5% band is an ID
evaluation objective, not a qualification gate.

## 21. Replay Limitations

Historical replay over `db/athena.db` is market-time deterministic when using
the ID-5E/5F/5G point-in-time readers, but it generally reads settled M5. It
cannot reconstruct the exact provider-provisional M5 values ATHENA saw live
unless a future knowledge-time evidence store is approved.

Impact:

- Positive qualification validation can be approximated with settled replay
  and then verified in shadow/live observation.
- Terminal disqualification validation is especially risky because it could
  appear safe in settled replay while live provisional evidence later changes.
- Persistence-across-bars confirmation policies need live shadow evidence if
  they depend on provisional M5.

## 22. Proposed Pure Engine Interface

Conceptual future interface:

```python
qualify(
    *,
    decision: Decision,
    session_context: SessionContext,
    intraday_signal_set: IntradaySignalSet,
    as_of: datetime,
    policy: EntryQualificationPolicy,
    provenance: EntryQualificationInputProvenance,
    latest_decision_id: str | None,
) -> EntryQualification
```

Requirements:

- No repository reads.
- No provider calls.
- No wall clock.
- No hidden config lookup.
- Explicit `as_of`.
- Explicit typed policy/config snapshot.
- Explicit provenance adapter input for indirect Decision finality.
- Output owns explanation and reason codes.

Do not pass the whole `WorkflowContext` into the engine.

## 23. Config / Methodology Versioning

Recommended shape:

- Add a frozen typed `EntryQualificationPolicy` in the future ID-6B
  implementation.
- Include `methodology_version`, for example
  `id6b-entry-qualification-v0`.
- Include `config_snapshot_id` supplied by the caller/run config context.
- Keep policy constants named and typed even when categorical, because
  "VWAP must be above" is still methodology.
- Do not create `config/entry_qualification.json` until the owner approves
  actual policy fields.

## 24. Reason-Code Architecture

ID-6A reason codes are structural. ID-6B should extend them only after policy
approval, grouped by category:

- Eligibility: non-candidate decision, superseded decision, session not
  applicable.
- Data quality: missing session context, missing signal set, stale evidence,
  unavailable M5/M15, provenance unknown.
- Positive readiness: above VWAP, bullish trend, RS support, RVOL support,
  OR support.
- Reversible negative readiness: below VWAP, mixed/bearish trend, no
  participation yet, OR not formed.
- Confirmation: policy not satisfied, waiting for persistence, insufficient
  independent support.
- Terminal: reserved; do not add flat terminal vocabulary until a terminal
  policy exists.

Every emitted state must be explainable without reconstructing rules in the
UI.

## 25. Validation Ladder

Owner-gated sequence:

1. Pure contract tests for all states, finality values, confirmation values,
   missing/stale behavior, and WATCH/TRADE binding.
2. Deterministic settled replay feasibility over selected recent sessions.
3. Evidence distributions and base rates across candidate Decisions.
4. Candidate-rule evaluation for proposed v0 policy.
5. Threshold analysis only if owner approves exploring numeric thresholds.
6. Chronological validation; no random train/test splitting.
7. Shadow/live observation because settled replay is not knowledge-time live
   reconstruction.
8. Owner promotion before dashboard/actionability use.

## 26. Performance

The future engine should be O(1) per candidate because it consumes
already-produced `Decision`, `SessionContext`, and `IntradaySignalSet`
objects. It should perform no N-by-M history reads, no provider calls, and no
market/sector refetch.

Any rule requiring fresh history queries inside the engine violates the
recommended architecture and should be moved upstream or rejected.

## 27. Persistence / Workflow Future Boundary

Deferred ownership:

- ID-6C: append-only persistence, latest-state read model, serialization,
  migration/tests.
- ID-6D: `entry_qualification` `WorkflowStage` after `decision`, `session`,
  and `intraday_analytics`.
- ID-6E: replay/shadow validation.

ID-6B.0 and the first ID-6B implementation must not create tables,
repositories, migrations, workflow dependencies, API/UI endpoints, or
scheduled behavior.

## 28. Risks

- Current Decision provenance is insufficient for stable indirect-M5
  finality claims.
- WATCH candidates lack a canonical `TradePlan`; qualified WATCH output may
  be actionable context but cannot become a trade plan in ID-6B.
- Hard OR/RS/RVOL gates may be either too sparse or redundant; distribution
  measurement must precede promotion.
- Settled replay cannot reproduce live provisional values.
- Existing ID artifacts are not persisted; historical artifact-state analysis
  requires rerunning engines.
- Outcome labels are too sparse for optimization.

## 29. Genuine Owner Decisions

1. Should ID-6B v0 be allowed to emit `QUALIFIED`?
   Alternatives: yes with categorical v0 policy; or emit only
   `UNKNOWN`/`NOT_YET` until shadow validation. Evidence: ADR-013 allows
   provisional positive qualification, but outcomes are sparse. Recommendation:
   yes, but only under an explicitly approved categorical v0 policy.

2. Which v0 confirmation rule should `CONFIRMED_BY_POLICY` mean?
   Alternatives: defer confirmation; or require above VWAP + bullish trend +
   one independent support from RS/RVOL. Evidence: VWAP/trend have current
   scoring relevance; RS/RVOL add participation context. Recommendation:
   approve the practical v0 only as provisional methodology, not as a tuned
   performance claim.

3. Should `DISQUALIFIED_FOR_SESSION` be used in initial ID-6B?
   Alternatives: no; or only for separately approved non-provisional terminal
   rules. Evidence: most intraday failures are reversible and M5 is
   provisional. Recommendation: no terminal state in v0 beyond lifecycle
   `EXPIRED`.

4. Should OR15/OR30 be mandatory?
   Alternatives: OR optional/contextual; OR15 mandatory; OR30 mandatory; either
   OR window can confirm. Evidence: OR overlaps price action and availability
   depends on session phase. Recommendation: contextual/support only until
   distribution analysis.

5. Should WATCH and TRADE have different intraday rules?
   Alternatives: same rule with preserved decision type; separate stricter
   WATCH policy; TRADE-only qualification. Evidence: no data supports stricter
   WATCH thresholds, and ADR-013 permits both. Recommendation: same evidence
   policy, different downstream interpretation.

## 30. Recommended ID-6B Implementation Slices

1. ID-6B.1: frozen typed policy/provenance input objects and reason-code
   extension proposal, no workflow/persistence.
2. ID-6B.2: pure engine implementation for eligibility, lifecycle,
   missing/UNKNOWN, finality aggregation, and owner-approved v0 readiness.
3. ID-6B.3: focused unit tests and deterministic fixture tests for WATCH,
   TRADE, missing/stale, provisional, and superseded cases.
4. ID-6B.4: read-only settled replay/distribution harness; no provider calls.
5. ID-6B.5: milestone review summary with measured base rates and owner
   promotion decision before ID-6C.

## 31. Recommendation

GO WITH CONDITIONS.

Conditions:

- Owner approves the v0 methodology choices in section 29.
- The initial engine stays pure and post-Decision.
- `DISQUALIFIED_FOR_SESSION` remains unused unless a stable terminal rule is
  separately approved.
- Indirect Decision provenance is treated conservatively.
- Any outcome/tuning work is deferred to validation/shadow milestones.

## Milestone Review Summary

**Name:** ID-6B.0 Entry Qualification Methodology / Engine Design

**Objective:** Determine the evidence-supported deterministic methodology and
future pure engine contract for deciding whether a canonical WATCH/TRADE
Decision is actionable now.

**Scope completed:** Recorded ID-6A owner approval, audited actual contracts,
runtime workflow, scoring/Decision overlap, session/intraday artifacts,
thresholds, persistence, and read-only historical data availability.

**Files created:**
`docs/research/ID-6B-ENTRY-QUALIFICATION-METHODOLOGY-DESIGN.md`.

**Files modified:** `docs/MILESTONES.md`,
`docs/ATHENA-ID-TRACK-HANDOFF.md`, `ATHENA_BRIEFING.md`,
`IMPLEMENTATION_SUMMARY.md`.

**Public APIs added:** None.

**Tests added:** None.

**Test results:** No pytest run; documentation-only discovery. Read-only
SQLite aggregate queries and `git diff --check` form the closeout validation.

**Coverage summary:** Not applicable; no production code changed.

**Architecture compliance:** Preserves ADR-013, ATHENA-002, ADR-003,
ADR-005, ADR-012, and the advisory-only/no-order boundary. No production
behavior changed.

**ADR compliance:** No new ADR is required for discovery. Future changes to
Decision, TradePlan, provider contracts, knowledge-time storage, EMR, DarvaX,
or broker/order behavior would require separate approval and are out of scope.

**Risks discovered:** Indirect Decision provenance is insufficient; outcome
labels are sparse; settled replay cannot reconstruct live provisional M5; hard
OR/RS/RVOL gates need measured base-rate evidence before promotion.

**Technical debt introduced:** None.

**Suggested improvements:** Approve or revise the section 29 methodology
choices, then implement the pure engine in small owner-gated slices.

**Remaining work:** Owner methodology review. Do not start engine
implementation, ID-6C, ID-6D, ID-6E, ID-7, EM-6, EMR, DarvaX, UI, provider,
DB, or production work until explicitly authorized.

**Commit message:**

```text
docs(review): define ID-6B entry qualification methodology

- Record ID-6A owner approval and open ID-6B.0 methodology review status.
- Add the Entry Qualification methodology design report for the future pure
  engine contract, provenance policy, and validation ladder.
- Preserve ADR-013, ID-5B CASE B, scoring, Decision, persistence, workflow,
  EMR, DarvaX, provider, and advisory-only boundaries.
```

**Ready for review:** Yes.
