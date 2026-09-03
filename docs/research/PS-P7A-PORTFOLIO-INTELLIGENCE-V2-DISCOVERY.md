# PS-P7A Portfolio Intelligence V2 Methodology & Evidence Discovery

Status: Owner/Chief Architect approved and frozen 2026-09-03
Date: 2026-09-03
Scope: Portfolio Intelligence V2 methodology/evidence inventory only
Boundary: No production code, schema, API, dashboard, Sync, import,
interpretation, scoring, decision, broker, transaction, or automatic-trading
changes

## 1. Executive Summary

My Portfolio V1 is complete and frozen. PS-P7A asks what V2 can safely add
without inventing evidence, duplicating ATHENA engines, or creating a second
DecisionEngine.

The smallest credible V2 path is not a broad portfolio-advisor rewrite. The
best near-term candidate is a narrow Conviction adapter that reuses the
already-approved Confidence semantics for the coherent Decision/session behind
each holding. Even that should be approved explicitly because confidence is
retrieved today from persisted run detail/report blocks rather than a dedicated
repository `ConfidenceAssessment` table.

Target 2/3 are not ready from the live DecisionEngine because it currently
builds one TradePlan target. Trend / Setup and Support 1 have typed candidate
evidence in intraday/scoring systems, but no approved Portfolio methodology for
turning those measurements into owner-facing holding fields. REDUCE and ROTATE
require explicit methodology; ROTATE is comparative and should be deferred to a
later Portfolio Advisor milestone.

## 2. Evidence Inventory

Approved and relevant evidence already exists:

- `Decision` with `decision_type`, `gate_results`, `trade_plan`, `score_ref`,
  `confidence_ref`, `risk_ref`, and canonical instrument/session identity.
- `TradePlan` with `entry_low`, `entry_high`, `stop_loss`, ordered
  `targets`, sizing/risk metadata, and validity window.
- `ConfidenceAssessment` with typed `overall_status`, `overall_value`,
  `overall_level`, dimensions, completeness, and explanation.
- `ScoringResult` with typed component scores, composite score, confluence
  inputs, and contribution traces.
- `EntryQualification`, persisted and Decision-bound, already used by V1 for
  ADD.
- Intraday typed evidence: `IntradaySignalSet`, `IntradayTrendContext`,
  `OpeningRangeEvidence`, `GapContext`, `RelativeStrengthContext`, and
  `RelativeVolumeContext`.
- Immutable My Portfolio snapshots with row/freshness/provenance/reason-code
  JSON and server-owned currentness.
- Legacy `portfolio/` and `analytics/portfolio/` engines for portfolio state
  and outcome/performance analytics.

Primary retrieval limitation: Decision rows persist references and TradePlan
JSON, and run records persist large detail/report JSON. There is no dedicated
repository table/read API for `ConfidenceAssessment`, `ScoringResult`, or
`IntradaySignalSet` as first-class portfolio-consumable artifacts.

## 3. Conviction Findings

`ConfidenceAssessment` is the strongest candidate for Portfolio Conviction. It
is typed, approved, explainable, and semantically close to "how trustworthy is
this Decision evidence." The existing dashboard/Decision services already read
confidence level/overall from persisted run-detail report blocks for a
Decision's `run_id`.

Classification: `ADAPTER REQUIRED`, possibly `INFRASTRUCTURE REQUIRED` if the
owner wants a first-class repository contract rather than reuse of run-detail
JSON.

Recommendation: do not create a Portfolio Conviction Score. If approved, PS-P7B
should map coherent Decision confidence directly:

- HIGH -> high conviction
- MEDIUM -> medium conviction
- LOW -> low conviction
- unavailable/stale/incoherent -> null with reason

This should preserve confidence as reliability semantics, not attractiveness or
position-sizing advice.

## 4. Trend / Setup Findings

ATHENA has multiple typed trend/setup-adjacent artifacts:

- `IntradayTrendContext` for 5m/15m directional agreement.
- Scoring technical-structure components and confluence inputs.
- Regime trend and market/sector context.
- Opening range relation/breakout event, gap, relative strength, and RVOL.
- Decision presentation text that uses "Trade setup" / "Watch setup" labels.

None is currently an approved Portfolio "Trend / Setup" field. DecisionType
alone is semantically insufficient: TRADE/WATCH says decision stance, not the
technical setup class. Intraday evidence is typed but descriptive and not
persisted as a first-class portfolio read artifact.

Classification: `METHODOLOGY REQUIRED` plus likely `INFRASTRUCTURE REQUIRED`
for durable retrieval.

Recommendation: keep Trend / Setup null until a dedicated classifier is
approved. A future milestone can define a deterministic taxonomy such as trend
continuation, pullback, breakout, retest, consolidation, or weakening only after
evidence sources and precedence are frozen.

## 5. Support 1 Findings

No approved ATHENA artifact was found that exactly means "nearest technical
support for a current holding." TradePlan `stop_loss` is already mapped to
Major Support / Exit and is semantically an invalidation/exit level, not
ordinary Support 1.

Potential raw inputs exist: swing lows/pivots could be derived from candles,
moving averages exist, Darvas boundaries exist in the DarvaX satellite, and
opening-range lows exist intraday. None is approved as Support 1 for Portfolio.

Classification: `METHODOLOGY REQUIRED`.

Recommendation: keep Support 1 null. Preserve TradePlan stop exclusively as
Exit/Invalidation evidence unless the owner approves a separate support
methodology.

## 6. Target 2 / Target 3 Findings

The domain `TradePlan` supports an ordered `targets` tuple, and serialization
preserves all target entries. However, the live `DecisionEngine._build_plan`
creates exactly one target from ATR target distance. V1 correctly consumes only
`targets[0]` as Target 1.

Classification: `DEFER` for current production, `READY` only for imported or
future decisions that already contain multiple approved ordered targets.

Recommendation: do not invent target extensions or risk/reward multiples. If
the owner confirms that future or external decisions may contain approved
multiple targets, PS-P7B may expose `targets[1]`/`targets[2]` only when present
on a coherent active TradePlan. Otherwise T2/T3 stay null.

## 7. REDUCE Findings

REDUCE is not currently derivable from V1's single-instrument rules without new
policy. Candidate inputs include confidence downgrade, failed gates, technical
deterioration, relative-strength deterioration, partial invalidation, target
achievement, concentration, and risk exposure. Each implies a different owner
policy about partial exits and position sizing.

Classification: `METHODOLOGY REQUIRED`.

Recommendation: do not include REDUCE in PS-P7B unless the owner first approves
whether REDUCE is single-instrument risk deterioration, portfolio-level
exposure management, or target-harvest behavior.

## 8. ROTATE Findings

ROTATE is inherently comparative: it means capital should move from holding A
to opportunity B. Existing ingredients include My Portfolio interpretations,
Top Opportunities Today, sector leadership, relative strength, composite score,
Decision state, EntryQualification, and freshness. But no approved methodology
connects them into a capital redeployment decision.

Classification: `METHODOLOGY REQUIRED` and likely `INFRASTRUCTURE REQUIRED`.

Recommendation: defer ROTATE to a later Portfolio Advisor milestone. Do not
implement lowest-holding-score to highest-watchlist-score shortcuts.

## 9. Portfolio-Level Intelligence Findings

V2 can eventually support holding strength ranking, concentration, sector
exposure, strongest/weakest holding, opportunity-cost warnings, and allocation
or risk concentration summaries. Existing `portfolio/` and
`analytics/portfolio/` packages are useful but are not directly aligned with
the frozen V1 imported-holdings snapshot model.

Classification: mostly `METHODOLOGY REQUIRED`; performance/history analytics
are `ADAPTER REQUIRED` after V1 snapshot history requirements are defined.

Recommendation: keep portfolio-level advisor concepts out of PS-P7B unless the
owner authorizes a dedicated methodology milestone.

## 10. Historical Analytics Findings

Immutable V1 snapshots now make historical analysis feasible: Status history,
Next Action history, P&L history, NAV-like trend, holding-level analysis
history, action transitions, stale/current analysis history, and sector
exposure over time. Existing Portfolio Analytics models can inform this work,
but V1 snapshots are the better source for My Portfolio analysis history.

Classification: `ADAPTER REQUIRED` for read-only history; `METHODOLOGY
REQUIRED` for outcome or recommendation-effectiveness claims.

Recommendation: defer UI/history work until after the first narrow V2 field
adapter is reviewed.

## 11. Existing Analytics Reuse Map

| Capability | Reuse Classification | Notes |
|---|---|---|
| `portfolio/my_portfolio_contracts.py` snapshot rows | REUSE | Frozen V1 20-column contract and reason/provenance model. |
| `portfolio/interpretation.py` | REUSE | Extend only through approved methodology/versioning; do not bypass. |
| `portfolio/sync.py` | ADAPT | Can pass additional retrieved evidence into interpreter after approval. |
| `confidence/` | ADAPTER REQUIRED | Approved semantics; needs coherent portfolio retrieval contract. |
| `scoring/` | METHODOLOGY REQUIRED | Rich components, but Portfolio field semantics not frozen. |
| `intraday/` evidence | METHODOLOGY REQUIRED | Typed/descriptive, not currently persisted for Portfolio consumption. |
| `entry_qualifications` | REUSE | Already frozen and consumed for ADD. |
| `analytics/portfolio/` | KEEP SEPARATE / ADAPT | Outcome/performance analytics, not interpretation methodology. |
| `api/v1/services/opportunities_service.py` | KEEP SEPARATE | Comparative opportunity presentation, not a rotation engine. |
| DarvaX | EXPERIMENTAL | Satellite evidence must not silently enter core Portfolio methodology. |

## 12. Coherency Requirements

Every V2 field must prove:

- same canonical `instrument_id`;
- snapshot holdings digest is current or explicitly reported stale/unknown;
- price session matches expected analysis session;
- Decision session matches price session;
- TradePlan is active for interpretation time;
- Confidence/scoring/report block belongs to the same Decision/run/cycle;
- EntryQualification, if used, matches Decision identity, run, cycle, type,
  instrument, and session;
- intraday evidence, if used, shares instrument, session_date, and `as_of`;
- unavailable evidence remains null with reason codes.

Portfolio must not interpret current price using stale methodology-sensitive
evidence.

## 13. Versioning Recommendation

Keep `portfolio-interpretation-v0` for V1 snapshots and for any V2 change that
only exposes already-approved evidence without changing interpretation meaning.

Bump to `portfolio-interpretation-v1` when a new methodology changes the
meaning or precedence of Status, Next Action, Conviction, Trend / Setup, Support
1, Target 2/3, REDUCE, ROTATE, or any other owner-facing action field.

Conviction-as-direct-Confidence-level may be an adapter-only change if the
owner confirms that the displayed label is literally Confidence semantics.
Trend/Support/REDUCE/ROTATE almost certainly require a v1 methodology.

## 14. V2 Candidate Classification Table

| Candidate | Classification | Recommendation |
|---|---|---|
| Conviction from coherent `ConfidenceAssessment.overall_level` | ADAPTER REQUIRED | Best PS-P7B candidate after owner approval. |
| Conviction score separate from Confidence | DEFER | Do not create a new score. |
| Trend / Setup from DecisionType | DEFER | Semantically insufficient. |
| Trend / Setup from intraday/scoring evidence | METHODOLOGY REQUIRED | Needs classifier and persistence/retrieval decision. |
| Support 1 from TradePlan stop | DEFER | Stop remains Exit/Invalidation. |
| Support 1 from pivots/MA/Darvas/OR lows | METHODOLOGY REQUIRED | Candidate raw evidence only. |
| Target 2/3 from additional TradePlan targets | READY if present; otherwise DEFER | Expose only existing ordered targets, never invent. |
| Target 2/3 synthetic extensions | DEFER | Explicitly not approved. |
| REDUCE | METHODOLOGY REQUIRED | Needs owner policy. |
| ROTATE | METHODOLOGY REQUIRED / INFRASTRUCTURE REQUIRED | Defer to Portfolio Advisor. |
| Snapshot history | ADAPTER REQUIRED | Read-only history feasible from immutable V1 snapshots. |
| Portfolio concentration/exposure | METHODOLOGY REQUIRED | Needs owner thresholds and data boundary. |
| Multi-worker DB lock | INFRASTRUCTURE REQUIRED | Separate operational hardening, not V2 methodology. |

## 15. P0/P1/P2/Deferred Gaps

P0: none found for starting V2 discovery.

P1:

- Confidence retrieval should be formalized if Conviction becomes PS-P7B.
- V2 coherency must define how run-detail evidence is matched to Decision and
  snapshot session.

P2:

- Snapshot history APIs may be useful before richer dashboard work.
- Analytics reuse needs a bridge between legacy portfolio models and V1
  imported holdings.

Deferred:

- Trend / Setup classifier.
- Support 1 methodology.
- REDUCE and ROTATE policy.
- Target ladder generation.
- Multi-worker database locking.

## 16. Explicit Owner Decisions With Recommendations

1. Is existing `ConfidenceAssessment` authoritative enough for Portfolio
   Conviction? Recommendation: yes, only if displayed as Confidence semantics.
2. If yes, may PS-P7B add only a retrieval/contract adapter? Recommendation:
   yes, keep it narrow.
3. Is any existing Trend/Setup artifact approved for Portfolio use?
   Recommendation: no; require a classifier methodology first.
4. Should Trend/Setup remain null until a dedicated classifier is approved?
   Recommendation: yes.
5. Is there an existing approved Support 1 source? Recommendation: no.
6. Should TradePlan stop remain exclusively Exit/Invalidation evidence?
   Recommendation: yes.
7. Does TradePlan already contain approved T2/T3? Recommendation: the domain
   allows multiple targets, but live DecisionEngine creates one; expose only if
   a coherent active plan already has them.
8. If not, should T2/T3 remain null? Recommendation: yes.
9. Is REDUCE a single-instrument interpretation or portfolio-level decision?
   Recommendation: decide explicitly before implementation.
10. Is ROTATE comparative and therefore deferred to a later Portfolio Advisor
    milestone? Recommendation: yes.
11. Which historical analytics should be prioritized after interpretation V2?
    Recommendation: snapshot history/status transitions before outcome claims.
12. Does any proposed change require `portfolio-interpretation-v1`?
    Recommendation: Conviction adapter may not; Trend/Support/REDUCE/ROTATE do.
13. Which candidate capability should become PS-P7B? Recommendation:
    Conviction adapter from coherent Confidence.
14. Should multi-worker DB locking remain separate infrastructure work?
    Recommendation: yes.

## 17. Smallest Recommended PS-P7B Scope

Recommended PS-P7B: Portfolio Conviction Adapter Discovery/Implementation,
limited to:

- retrieve the coherent Decision's existing confidence report block;
- verify Decision/run/session coherency;
- map only `ConfidenceAssessment.overall_level` into the Portfolio Conviction
  column;
- keep null when confidence is absent, stale, or incoherent;
- add reason/provenance codes;
- do not change Status, Next Action, Support, Trend, Target, REDUCE, ROTATE, or
  core Decision methodology.

If the owner rejects run-detail JSON as an adequate source, PS-P7B should become
an infrastructure milestone to persist/retrieve ConfidenceAssessment cleanly
before any UI field is filled.

## 18. Files Changed

- `docs/research/PS-P7A-PORTFOLIO-INTELLIGENCE-V2-DISCOVERY.md`
- `docs/research/PS-P6C-MY-PORTFOLIO-V1-END-TO-END-VALIDATION.md`
- `docs/MILESTONES.md`
- `IMPLEMENTATION_SUMMARY.md`
- `ATHENA_BRIEFING.md`

## 19. Validation Result

PS-P7A is documentation/discovery only. No production code, schema, API,
dashboard, import, Sync, or methodology files were changed.

Validation:

- `rtk git diff --check` passed.

## 20. Suggested Documentation Commit Message

```text
docs(portfolio): freeze V1 and discover Portfolio Intelligence V2

- Record Owner/Chief Architect approval of PS-P6C and declare My Portfolio V1 complete and frozen.
- Add PS-P7A discovery for V2 evidence, methodology, coherency, versioning, and candidate scope.
- Recommend a narrow Conviction adapter as the smallest possible PS-P7B pending owner approval.
```
