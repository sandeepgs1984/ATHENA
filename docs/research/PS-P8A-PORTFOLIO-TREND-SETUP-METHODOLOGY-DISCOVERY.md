# ATHENA Portfolio Sync - PS-P8A Trend / Setup Methodology Discovery

**Date:** 2026-09-04
**Branch:** `feature/portfolio-sync`
**Milestone:** PS-P8A - discovery only
**Status:** Ready for Owner / Chief Architect review

---

## 1. Executive Summary

PS-P8A audited whether ATHENA can honestly populate the existing My Portfolio
`Trend / Setup` column after PS-P7B froze Conviction. The answer is: not yet as
a production portfolio field.

ATHENA has several strong evidence families that sound related to trend/setup:
D1 indicators and scoring, intraday VWAP/M5/M15 trend, EntryQualification,
relative strength / relative volume, Decision and TradePlan, and DarvaX
price-action primitives. None of them is currently an approved, stable,
portfolio-holding-level semantic taxonomy for "what setup am I holding?"

Recommendation: keep `Trend / Setup` unavailable under
`portfolio-interpretation-v1`; use PS-P8B to freeze a narrow taxonomy and replay
validation plan before implementation. No production code change is authorized
by this discovery milestone.

## 2. Evidence Inventory

| Evidence family | Current artifact | Reusable for PS-P8B? | Classification |
|---|---|---:|---|
| D1 technical indicators | `IndicatorResult` for SMA, EMA, RSI, ATR, MACD, ADX, VOLUME_MA, VWAP | Yes, with semantics frozen | Approved measurements, not setup labels |
| D1 scoring | `ScoringResult.components["trend"]`, `technical_structure`, `momentum`, composite | Yes, as evidence only | Approved score inputs, not taxonomy |
| Decision | `Decision.decision_type`, gates, explanation | Yes | Canonical current advisory conclusion |
| TradePlan | entry band, stop, target 1, validity | Partly | Current actionable plan, not setup type |
| EntryQualification | `EntryQualification.state`, reason codes, methodology version | Partly | Intraday actionability, not holding trend |
| Intraday trend | `IntradayTrendContext.trend_label` | Partly | M5/M15 point-in-time trend only |
| VWAP | `VwapRelation` | Partly | Session relation only |
| Relative strength | `RelativeStrengthContext` | Partly | Point-in-time comparative performance only |
| Relative volume | `RelativeVolumeContext` | Partly | Same-time-of-day volume context only |
| Market / sector context | regime, market health, sector health | Supporting only | Backdrop, not per-holding setup |
| DarvaX | isolated price-action satellite | No direct reuse | Experimental / isolated per ADR-010 |
| Portfolio history | My Portfolio snapshots | Future use | Current V1 snapshot history exists; trend persistence semantics not frozen |

## 3. Existing Technical Structure Models

ATHENA currently computes technical structure in layers:

- `IndicatorEngine` produces immutable measurements only. Its docstring states
  that indicators never imply bullishness, bearishness, strength, or weakness.
- `ScoringEngine._trend` combines regime trend, ADX, and optional intraday
  confluence into a numeric component score.
- `ScoringEngine._technical_structure` reads price-vs-SMA, MACD histogram, and
  session VWAP deviation into another numeric component score.
- `DecisionEngine` then consumes scores and gates to produce canonical
  `Decision` objects.
- `PortfolioInterpreter` consumes only already-accepted portfolio evidence and
  currently emits `trend_setup=None` with `TREND_SETUP_NOT_AVAILABLE`.

This is a good foundation, but it is not a setup classifier. A high trend score
does not tell whether the holding is a breakout, pullback, base, reversal,
failed setup, continuation, or range-bound consolidation.

## 4. D1 vs Intraday Findings

D1 and intraday evidence answer different questions.

D1 evidence is appropriate for portfolio-holding posture because My Portfolio is
a current holdings view, not an intraday entry ticket. D1 can support stable
trend states such as above/below moving averages, momentum quality, ADX
strength, and stop/target context.

Intraday evidence is useful for "is it actionable now?" It should not dominate
a portfolio `Trend / Setup` label because:

- `IntradayTrendContext` is explicitly M5/M15 only.
- VWAP is a same-session relation.
- EntryQualification is checkpoint-sensitive and historically flickers by
  design; it is not a durable holding setup label.
- Relative strength and relative volume are point-in-time observations, not
  persistent classification.

PS-P8B should therefore treat D1 as the primary timeframe and intraday as a
secondary qualifier only when the taxonomy explicitly says so.

## 5. Trend / Setup Findings

The current codebase does not contain an approved semantic vocabulary for
portfolio trend/setup. The exposed API field exists, and the dashboard renders
it, but PS-P5B/PS-P7B correctly left it unavailable.

Candidate label families found during discovery:

- Trend-only labels: `UPTREND`, `DOWNTREND`, `SIDEWAYS`, `UNKNOWN`.
- Structure labels: `BREAKOUT`, `PULLBACK`, `CONSOLIDATION`, `REVERSAL`,
  `FAILED_STRUCTURE`.
- Portfolio-friendly combined labels: `UPTREND_BREAKOUT`,
  `UPTREND_PULLBACK`, `RANGE_CONSOLIDATION`, `DOWNTREND_AT_RISK`.

These are not implementation recommendations yet. They are candidate semantics
for owner review. PS-P8A does not freeze them.

## 6. Decision / Scoring Findings

Decision and scoring evidence is valuable but must be used carefully:

- A current `TRADE` decision with an active `TradePlan` can support that a setup
  exists, but the setup type still requires independent structure semantics.
- A current `WATCH` decision can support "structure intact / not actionable"
  posture, but it should not become a setup label by itself.
- Failed quality gates belong in Status/Next Action caution logic first; they
  should not be hidden inside a trend/setup label.
- Scores can provide confidence in a label only if the label's underlying
  evidence remains visible and coherent.

PS-P8B should avoid deriving `Trend / Setup` directly from the final composite
score. The label should be a transparent classification over named evidence.

## 7. EntryQualification Findings

`EntryQualificationEngine` implements a frozen v0 intraday readiness expression:

`VWAP positive AND aggregate intraday trend BULLISH AND (RS support OR RVOL support)`.

That is useful for My Portfolio's ADD behavior, already consumed by the
Portfolio interpreter. It should not become the Trend/Setup field because:

- it is intraday and point-in-time;
- it answers actionability, not structure identity;
- it depends on session phase;
- it can be `NOT_YET`, `QUALIFIED`, `UNKNOWN`, or `EXPIRED` without saying what
  the underlying D1 setup is.

PS-P8B can cite EntryQualification as an intraday qualifier, for example
"pullback, intraday not ready", but not as the source taxonomy.

## 8. Relative Strength Findings

`RelativeStrengthContext` is a clean comparative measurement. It is not RSI and
not a score. The contract intentionally uses sign-only relations:
`OUTPERFORMING`, `UNDERPERFORMING`, `MATCHING`, `UNKNOWN`.

For PS-P8B, relative strength is best treated as a modifier:

- it can support a stronger trend/setup interpretation when D1 structure is
  already classified;
- it can warn when a holding underperforms its sector/market;
- it should not create a setup label on its own.

## 9. DarvaX Classification

DarvaX contains useful price-action primitives: boxes, swings, ATH distance,
range contraction, volume expansion, inside bars, Fibonacci levels, and a
50/100 EMA trend context. However, ADR-010 and the package docstrings are clear:
DarvaX is an isolated, opt-in satellite and never feeds ATHENA scoring,
confidence, risk, Decision, TradePlan, universe, or canonical pipeline behavior.

Classification for Portfolio V2:

- DarvaX is `TRACK_ISOLATED`.
- DarvaX evidence is `NOT_APPROVED_AS_PORTFOLIO_INPUT`.
- DarvaX can inspire owner-reviewed taxonomy language.
- Direct use in My Portfolio would require a separately approved boundary
  decision, likely ADR-level if ATHENA core must consume DarvaX outputs.

## 10. Persistence / Retrieval Gaps

The current repository supports the ingredients but not a frozen persisted
trend/setup artifact:

- D1 and intraday candles are persisted and retrievable point-in-time.
- Decision reports are retrievable through `get_run_detail()` and the
  `decision_reports` pipeline payload.
- EntryQualification has durable append-only persistence.
- My Portfolio snapshots persist immutable row values and provenance.
- No canonical `PortfolioTrendSetup` object/table/version exists.
- No durable setup taxonomy, reason-code vocabulary, precedence ordering, or
  replay harness exists for this field.

PS-P8B should decide whether `Trend / Setup` remains a derived row field only or
needs its own typed evidence/result object before storage.

## 11. Proposed Semantic / Taxonomy Direction

The safest PS-P8B design direction is a two-layer semantic model:

1. **Trend state** from D1 structure only:
   `UPTREND`, `DOWNTREND`, `SIDEWAYS`, `UNKNOWN`.
2. **Setup state** from price/indicator/decision context:
   `BREAKOUT`, `PULLBACK`, `CONSOLIDATION`, `REVERSAL_ATTEMPT`,
   `FAILED_STRUCTURE`, `UNKNOWN`.

Precedence should be explicit and owner-approved. A conservative candidate:

1. Data/coherency failure -> `UNKNOWN`.
2. Stop/major invalidation breached -> `FAILED_STRUCTURE`.
3. D1 trend unavailable -> `UNKNOWN`.
4. Price materially above D1 moving average + supportive momentum -> trend label
   only unless breakout/pullback criteria are frozen.
5. Active TradePlan can expose "setup active" only after D1 setup criteria agree.
6. Intraday EntryQualification can suffix actionability, never replace the D1
   label.

No numeric thresholds are proposed here because PS-P8A is discovery only. Any
threshold must come from existing config or a PS-P8B owner-approved method.

## 12. Missing / Stale Evidence Policy

Recommended PS-P8B policy:

- Missing D1 candles or indicators -> `Trend / Setup` unavailable.
- Stale Decision evidence -> unavailable or label with stale reason, depending
  on owner preference.
- Intraday-only freshness failure -> do not suppress a D1 label, but suppress
  any intraday/actionability suffix.
- Incoherent Decision/Confidence/EntryQualification evidence -> do not use that
  artifact for labeling.
- Never downgrade `UNKNOWN` to `SIDEWAYS`; sideways must be measured.

## 13. Coherency Rules

The field needs the same coherency discipline PS-P7B applied to Conviction:

- same instrument;
- same or explicitly compatible session date;
- no future evidence relative to the snapshot `as_of`;
- no stale/superseded Decision silently used;
- methodology version persisted in row provenance;
- reason codes name which evidence was included/excluded.

## 14. Version Recommendation

Do not change `PORTFOLIO_INTERPRETATION_VERSION` in PS-P8A.

Recommended future implementation version:

- Keep current output as `portfolio-interpretation-v1`.
- If PS-P8B freezes and PS-P8C implements Trend/Setup, bump to
  `portfolio-interpretation-v2`.
- Persist reason codes such as `TREND_SETUP_FROM_D1_STRUCTURE`,
  `TREND_SETUP_D1_UNAVAILABLE`, `TREND_SETUP_INTRADAY_QUALIFIER_UNAVAILABLE`,
  and `TREND_SETUP_EVIDENCE_INCOHERENT`.

## 15. Historical / Replay Validation

Before production implementation, PS-P8B should require validation on replayed
historical snapshots:

- label stability across consecutive D1 sessions;
- no future candle leakage;
- no label changes caused solely by missing intraday evidence;
- no DarvaX/EMR dependency;
- deterministic re-run equality for the same snapshot inputs;
- owner-inspection sample across `TRADE`, `WATCH`, `NO_TRADE`, stale, missing
  price, and stop-breached holdings.

This should be a methodology gate before any dashboard/API change.

## 16. Classification Table

| Candidate input | Classification | Reason |
|---|---|---|
| D1 SMA/EMA/MACD/ADX/RSI/ATR | `APPROVED_MEASUREMENT` | Deterministic indicator layer, but not labels |
| Scoring trend component | `APPROVED_EVIDENCE` | Explains strength, not setup identity |
| Scoring technical_structure | `APPROVED_EVIDENCE` | Price-vs-SMA/MACD/VWAP support, not taxonomy |
| Current Decision | `APPROVED_CONTEXT` | Current recommendation context |
| Active TradePlan | `APPROVED_CONTEXT` | Entry/stop/target 1 and validity only |
| EntryQualification | `INTRADAY_QUALIFIER` | Actionability, not trend/setup |
| Relative Strength | `SECONDARY_MODIFIER` | Comparative performance only |
| Relative Volume | `SECONDARY_MODIFIER` | Intraday volume support only |
| Market / sector health | `BACKDROP_ONLY` | Not per-holding setup |
| DarvaX | `TRACK_ISOLATED` | ADR-010 forbids core consumption |
| EMR | `OUT_OF_SCOPE` | Separate isolated research/live-shadow track |

## 17. Owner Decisions Needed

PS-P8B should ask the owner to decide:

1. Should `Trend / Setup` be one combined label or two semantic dimensions
   rendered in one column?
2. Should labels be D1-first only, or may intraday evidence modify visible text?
3. Which initial taxonomy is acceptable for V2: trend-only, setup-only, or
   combined trend+setup?
4. Should active `TradePlan` be required before any setup label is shown?
5. Should DarvaX remain inspiration-only, or should a future ADR explore a legal
   adapter boundary?
6. What replay acceptance threshold proves the taxonomy is stable enough?

## 18. Recommended PS-P8B Scope

Recommended next milestone:

**PS-P8B - Portfolio Trend / Setup Methodology Freeze**

Scope:

- freeze semantic vocabulary;
- freeze evidence eligibility and precedence;
- freeze null/stale/incoherent policy;
- freeze reason codes;
- freeze version bump rule;
- define deterministic replay validation fixtures;
- produce review-ready examples for current holdings.

Explicitly out of scope for PS-P8B:

- no production code;
- no dashboard/API changes;
- no new persistence table;
- no DarvaX/EMR coupling;
- no order-placement or execution behavior.

## 19. Files Changed

Created:

- `docs/research/PS-P8A-PORTFOLIO-TREND-SETUP-METHODOLOGY-DISCOVERY.md`

Modified:

- `docs/MILESTONES.md`
- `IMPLEMENTATION_SUMMARY.md`
- `ATHENA_BRIEFING.md`

No `src/athena` production code was changed for PS-P8A.

## 20. Validation

Planned validation for this documentation-only milestone:

- `git diff --check`
- `git status --short src/athena`
- conflict-marker search across touched documents

No pytest or Ruff run is required because PS-P8A changes no executable code.

## 21. Suggested Commit Message

```text
docs(portfolio): discover Portfolio Trend Setup methodology

- Add PS-P8A discovery for the My Portfolio Trend / Setup field after PS-P7B freeze.
- Classify D1, intraday, Decision, EntryQualification, relative strength, and DarvaX evidence so PS-P8B can freeze a safe taxonomy.
- Keep production Portfolio interpretation unchanged because no Trend / Setup methodology is approved yet.
```
