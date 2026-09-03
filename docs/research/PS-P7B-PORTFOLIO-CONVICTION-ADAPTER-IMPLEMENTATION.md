# PS-P7B Portfolio Conviction Adapter Implementation

Status: Implementation complete; ready for Owner/Chief Architect review
Date: 2026-09-03
Scope: Portfolio Conviction only
Boundary: No Status, Next Action, Trend / Setup, Support 1, Target 2/3,
REDUCE, ROTATE, allocation, ranking, history, schema, broker, or order behavior
changes

## 1. Executive Summary

PS-P7B implements the first approved Portfolio Intelligence V2 field:
Conviction. Conviction is a direct categorical mapping from the coherent
Decision's persisted ATHENA Confidence level. It is not a new portfolio score,
not a buy-strength signal, not a sizing input, and not an allocation or ranking
mechanism.

New My Portfolio snapshots now use `portfolio-interpretation-v1`. Historical
V0 snapshots remain immutable and are read back from their stored row/provenance
JSON without migration or backfill.

## 2. Frozen Owner Decisions

- PS-P7A is Owner/Chief Architect approved and frozen 2026-09-03.
- My Portfolio V1 remains complete and frozen.
- PS-P7B may populate only Conviction.
- Conviction must map only from `ConfidenceAssessment.overall_level`.
- Missing, legacy, malformed, stale, or incoherent Confidence yields null.
- Conviction must not influence Status, Next Action, ADD, EXIT, Key Trigger,
  Major Support / Exit, or Target 1.
- Target 2/3, Trend / Setup, Support 1, REDUCE, ROTATE, allocation, ranking,
  and portfolio-level advisor logic remain deferred.

## 3. Confidence Source

The approved source is the existing persisted DecisionReport confidence block
inside run detail JSON:

- `runs.detail_json`
- optional top-level or nested `pipeline`
- `decision_reports[decision.decision_id].confidence`
- `confidence.status == "OK"`
- `confidence.level in HIGH/MEDIUM/LOW`

The code now reuses `athena.confidence.report_lookup` for the persisted report
shape. No database schema or new Confidence table was required.

## 4. Existing Retrieval Reuse

Existing retrieval was found in:

- `DecisionsService._load_confidence_levels`
- `DecisionsService._fetch_report`
- `OpportunitiesService._fetch_report`

PS-P7B extracted the common DecisionReport confidence-level mapping used by
`DecisionsService` into `athena.confidence.report_lookup`. Portfolio then uses
a dedicated `PortfolioConfidenceAdapter` rather than parsing run detail inside
Sync, API handlers, the interpreter, or dashboard JavaScript.

## 5. Adapter Architecture

`PortfolioConfidenceAdapter` is a server-side read adapter over
`SqliteRepository.get_run_detail`. It accepts the already-selected Decision and
Portfolio coherency facts from Sync, retrieves the Decision's own run detail,
and returns compact typed `PortfolioConfidenceEvidence`.

The adapter caches parsed pipeline detail per run during one Sync orchestrator
instance. It never searches older runs and never substitutes another Decision's
confidence report.

## 6. Coherency Rules

Conviction is eligible only when:

- the Portfolio row has an accepted Decision,
- the Decision's instrument matches the holding,
- the Decision passed existing current-session coherency,
- the Confidence report is found under that same Decision's `run_id`,
- the report key is the same `decision_id`, and
- the report has a supported HIGH/MEDIUM/LOW level.

If the Decision is stale or incoherent, Conviction is null even if the old run
contains Confidence.

## 7. Conviction Mapping

The mapping is intentionally direct:

| Confidence level | Portfolio Conviction |
|---|---|
| HIGH | HIGH |
| MEDIUM | MEDIUM |
| LOW | LOW |

No numeric percentages, composites, score fallback, or Portfolio-specific
Conviction score were added.

## 8. Missing/Legacy Evidence

Missing run detail, missing DecisionReport, missing confidence block, `UNKNOWN`
confidence, unsupported level, and legacy/malformed payloads all yield:

- `conviction = null`
- `CONVICTION_CONFIDENCE_UNAVAILABLE` or
  `CONVICTION_CONFIDENCE_INCOHERENT`
- the rest of the Portfolio row remains usable when its own inputs are usable

Missing Confidence alone does not convert Sync to PARTIAL or FAILED.

## 9. Error Isolation

The adapter catches unexpected run-detail retrieval failures and returns typed
unavailable evidence. It does not fail valuation, Status, Next Action, TradePlan
fields, or row persistence.

## 10. Reason Codes

PS-P7B adds the smallest reason-code set needed for Conviction auditability:

- `CONVICTION_FROM_CONFIDENCE`
- `CONVICTION_CONFIDENCE_UNAVAILABLE`
- `CONVICTION_CONFIDENCE_INCOHERENT`

Legacy `CONFIDENCE_EVIDENCE_UNAVAILABLE` remains available for older persisted
snapshots and compatibility, but new V1 interpreter output uses the PS-P7B
codes.

## 11. Provenance

Portfolio row `interpretation_evidence` now records compact Confidence
provenance:

- Decision ID
- run ID
- source (`decision_report.confidence`)
- resolved level
- coherency flag
- adapter reason

The large Confidence report is not duplicated into every Portfolio snapshot.

## 12. Interpretation v1

`PORTFOLIO_INTERPRETATION_VERSION` is now
`portfolio-interpretation-v1`. The pure interpreter maps only typed
`ConfidenceLevel` evidence to Conviction and remains free of repository access,
DB reads, provider calls, DecisionEngine calls, ScoringEngine calls, and raw
run-detail JSON parsing.

## 13. Historical Compatibility

Historical snapshots keep their stored rows and stored provenance. No migration,
backfill, recomputation, or historical row rewrite was added.

## 14. Currentness Compatibility

PS-P6B currentness remains unchanged. `CURRENT`, `STALE_HOLDINGS_CHANGED`, and
`UNKNOWN` still derive from holdings-digest/currentness semantics. Conviction is
a historical field on the snapshot row and does not affect currentness.

## 15. Dashboard Presentation

The existing Conviction column is populated from the API field. The dashboard
renders HIGH/MEDIUM/LOW or `-` and adds a compact title explaining that
Conviction reflects ATHENA Decision confidence/reliability, not buy strength.
No client-side methodology or scoring was added.

## 16. Tests

Added adapter, interpreter, Sync/API, and dashboard contract coverage:

- HIGH/MEDIUM/LOW direct mapping
- missing Confidence
- stale Decision
- wrong DecisionReport key / no fallback
- malformed legacy payload
- ADD independence
- EXIT independence
- Status/action/TradePlan independence
- currentness regression through existing PS-P6B cases

## 17. Regression

Focused PS-P7B/My Portfolio suite:

`70 passed, 2 warnings`

Dashboard contract:

`1 passed, 2 warnings`

Combined post-fix focused regression:

`71 passed, 2 warnings`

Full repository suite:

`3263 passed, 2 warnings`

Warnings are existing FastAPI/Starlette deprecations from the test client stack.

## 18. Explicitly Deferred Fields

The following remain out of scope and unchanged:

- Trend / Setup remains null
- Support 1 remains null
- Target 2 remains null
- Target 3 remains null
- REDUCE absent
- ROTATE absent
- portfolio-level ranking/allocation absent
- no DecisionEngine, ScoringEngine, Risk, Confidence methodology change

## 19. Known Limitations

Conviction can be populated only when a supported DecisionReport confidence
block exists in the Decision's own run detail. Older runs without that persisted
shape remain null. There is still no first-class ConfidenceAssessment table;
PS-P7B intentionally avoided adding one because the approved persisted source
was sufficient.

Project-wide Ruff still reports unrelated historical lint debt outside this
milestone. Touched-file Ruff passed. Project-wide mypy is blocked by unrelated
third-party/stub and pre-existing strict typing issues; the new Portfolio and
confidence source files pass local mypy.

## 20. Recommended Next Milestone

Stop for Owner/Chief Architect review. The next milestone should be chosen
explicitly after PS-P7B review. Likely candidates are PS-P8A Trend/Setup
methodology discovery, Support methodology discovery, or snapshot/history
analytics discovery.

## Suggested Commit Message

```text
feat(portfolio): add Portfolio Conviction adapter

- Freeze PS-P7A and record My Portfolio V1 as still complete and frozen.
- Reuse persisted DecisionReport confidence lookup through a shared helper and
  dedicated Portfolio confidence adapter.
- Populate Conviction from coherent HIGH/MEDIUM/LOW Confidence only and bump
  new snapshot interpretation output to portfolio-interpretation-v1.
- Preserve Status, Next Action, ADD, EXIT, currentness, schema, and deferred
  Portfolio Intelligence fields.
```
