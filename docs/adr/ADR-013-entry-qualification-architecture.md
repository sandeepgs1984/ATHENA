# ADR-013 - Entry Qualification Architecture

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-09-02 |
| Owners | Chief Architect / Project Owner |
| Scope | Intraday Intelligence ID-6 Entry Qualification architecture |

## Context

ATHENA's canonical `Decision` remains the daily/structural authority for what
is worth watching or trading. ID-0 through ID-5 added intraday evidence,
session context, point-in-time market-time retrieval safety, and live M5
settlement evidence without changing scoring, confidence, risk, `Decision`,
`TradePlan`, provider contracts, EMR, DarvaX, UI, or broker behavior.

ID-5B closed with the owner-approved final classification
`CASE_B_CONTENT_CHANGES`: current-session Kite M5 candles can be
market-time closed yet later differ from provider-settled historical M5. That
does not make live M5 unusable, but it prevents ATHENA from treating it as
provider-final evidence for irreversible intraday qualification decisions.

ID-6 discovery was owner-approved with a condition: before implementation,
Entry Qualification needs an ADR because it introduces a new persisted
decision-relevant concept, a new live workflow stage, and a new architectural
boundary between canonical daily `Decision` and intraday actionability. This
ADR satisfies that governance prerequisite. It does not implement ID-6A code.

## Decision

ATHENA will add Entry Qualification as a distinct, advisory-only Intraday
Intelligence concept that evaluates whether an already-produced canonical
`Decision` is actionable in the current session.

The responsibility boundaries are:

1. Daily/Structural `Decision`: what is worth watching or trading.
2. Entry Qualification: whether that candidate is actionable now.
3. Entry/Execution planning: when, at what price, and with what risk structure.
4. Live Plan Supervision: whether a previously prepared plan remains valid.

Entry Qualification will not promote a canonical `Decision`, change a
`Decision` type, create an entry price, create a stop, create targets, size a
position, place orders, modify EMR, modify DarvaX, or alter canonical ATHENA
scoring, confidence, risk, eligibility, `DecisionEngine`, or `TradePlan`
behavior. `EntryQualification.QUALIFIED` is not equivalent to
`DecisionType.TRADE`.

Entry Qualification will be a persisted decision-relevant artifact bound to a
canonical `Decision`. Its implementation must preserve provenance sufficient
to identify the instrument, bound decision, run or cycle, decision type,
qualification state, evidence reliability, reason codes or evidence
references, `as_of`, methodology/configuration provenance, and explanation.
This ADR freezes the conceptual provenance contract only; it does not define a
physical schema or final field names.

Qualification state and evidence reliability are orthogonal dimensions. The
approved state family is:

- `OUT_OF_SCOPE`
- `UNKNOWN`
- `NOT_YET`
- `QUALIFIED`
- `DISQUALIFIED_FOR_SESSION`
- `EXPIRED`

The approved reliability family is:

- `UNKNOWN_RELIABILITY`
- `LIVE_M5_PROVISIONAL`
- `CONFIRMED_BY_POLICY`
- `STABLE_NON_M5`

State names must not encode reliability. In particular, names such as
`QUALIFIED_PROVISIONAL` and `QUALIFIED_CONFIRMED` are rejected.

`CONFIRMED_BY_POLICY` means an owner-approved Entry Qualification methodology
confirmation contract has been satisfied. It does not mean provider-settled,
historically final, immutable, bitemporal, or confirmed by multiple signal
families unless a later owner-approved methodology explicitly says so.

Current-session live M5 provisionality must be handled across both direct and
indirect paths:

- Direct path: M5 -> `IntradaySignalSet` -> Entry Qualification.
- Indirect path: M5 -> VWAP/confluence -> `ScoringEngine` -> canonical
  `Decision` -> Entry Qualification.

Market-time safety, candle completion, provider finality, qualification
confirmation, and knowledge-time replay are separate concerns. No irreversible
ID-6 state may be caused directly or indirectly solely by provider-provisional
live M5 evidence. ID-6 must not round, resample, repair, synthesize, normalize,
forward-fill, or nearest-match current-session evidence to hide that
provisionality.

Entry Qualification evaluates a specific canonical `Decision`. The canonical
`Decision` remains the daily/structural authority and Entry Qualification never
promotes `WATCH` to `TRADE`. Both `WATCH` and `TRADE` decisions may enter the
Entry Qualification funnel. A qualified `WATCH` means only that the WATCH
candidate currently satisfies intraday actionability policy; any future
`IntradayTradePlan` policy for WATCH candidates is deferred.

A newer canonical `Decision` supersedes the identity and freshness of older
Entry Qualification results for the same instrument. Older observations remain
audit evidence. If a newer decision is downgraded solely because of
provider-provisional live M5 influence, that downgrade must not automatically
create an irreversible ID-6 rejection.

The state lifecycle semantics are:

- `OUT_OF_SCOPE`: the canonical decision type or context is not eligible for
  Entry Qualification.
- `UNKNOWN`: required evidence is unavailable, stale, insufficient, or
  reliability cannot be established.
- `NOT_YET`: the candidate is in scope, but actionability conditions are not
  currently satisfied and the session can still produce a valid setup.
- `QUALIFIED`: the candidate currently satisfies the approved intraday
  actionability policy.
- `DISQUALIFIED_FOR_SESSION`: the candidate has violated an approved session
  invalidation condition that cannot be repaired later in the same session.
- `EXPIRED`: the qualification result is no longer fresh for the current
  decision/session/cycle, including supersession by a newer canonical decision
  or session boundary expiry.

Future workflow integration must use ATHENA's live `WorkflowStage` mechanism
with an explicit `entry_qualification` stage. The minimum dependency set is
`depends_on=("decision", "session", "intraday_analytics")`. If the
implementation needs direct provenance not carried by `IntradaySignalSet`, it
must declare additional explicit dependencies rather than reaching around the
workflow graph. This ADR does not authorize a scheduler, a new pipeline, new
Decision inputs, or order behavior.

Persistence must make Entry Qualification independently queryable and
auditable. The preferred implementation shape is append-only observations, a
latest-state read model, and reason codes plus explanations captured at
creation time, consistent with ADR-005. Entry Qualification auditability is not
the same as full knowledge-time market-data replay. Knowledge-time/bitemporal
market-data storage remains outside this ADR.

Replay must remain deterministic. Analytical logic must be pure over explicit
inputs, injected clocks, and declared `as_of` values. Historical replay that
uses settled historical M5 must label the limitation that it cannot reconstruct
the exact provider-provisional live M5 values observed at market time unless a
future knowledge-time evidence store is approved.

Non-goals:

- ID-6A Python types, schema, repositories, migrations, engines, thresholds,
  workflow wiring, UI, or tests.
- Entry price, stop, targets, sizing, order placement, broker writes, or
  execution automation.
- Changes to `ScoringEngine`, `DecisionEngine`, canonical `Decision`,
  `TradePlan`, confidence, risk, eligibility, EMR, DarvaX, or canonical
  ATHENA methodology.
- Provider requests, raw artifact mutation, M5 repair, resampling,
  normalization, rounding, forward-fill, or synthesis.
- Knowledge-time/bitemporal market-data replay storage.

The owner-gated implementation sequence is:

1. ID-6A0: this ADR.
2. ID-6A: domain/state/reliability contract.
3. ID-6B: pure deterministic qualification engine.
4. ID-6C: persistence and auditability.
5. ID-6D: workflow integration.
6. ID-6E: replay/shadow validation.

Each slice requires owner approval before the next begins.

## Alternatives considered

1. **No ADR; treat package placement as enough.** Rejected because ID-0
   identified that a new intraday decision-relevant concept requires explicit
   architectural approval under ATHENA-002.
2. **Amend ADR-003 only.** Rejected because ADR-003 governs pipeline context
   and workflow mechanics, while Entry Qualification is a new domain concept
   and persisted decision-relevant artifact.
3. **Fold Entry Qualification into `DecisionEngine`.** Rejected because it
   would blur daily structural authority with intraday actionability and risk
   changing canonical Decision semantics.
4. **Encode reliability inside state names.** Rejected because live-M5
   provisionality and actionability are separate facts; combining them creates
   ambiguous lifecycle behavior.
5. **Treat live M5 as either final or unusable.** Rejected because ID-5B shows
   a narrower reality: live M5 is useful evidence but not provider-final
   evidence for irreversible qualification states.

## Consequences

Entry Qualification now has an explicit architectural boundary before any
production code is written. Future ID-6A code can be reviewed against a frozen
conceptual contract instead of rediscovering the boundary during
implementation.

This adds one governance step before ID-6A, but it prevents Entry
Qualification from silently contaminating canonical Decision, TradePlan, EMR,
DarvaX, broker, or order behavior.

Physical schema, final DTO fields, thresholds, confirmation policy, WATCH
trade-plan treatment, and knowledge-time replay storage remain deferred to
separate owner-gated milestones or ADR review where required.
