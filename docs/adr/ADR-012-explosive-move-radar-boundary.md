# ADR-012 - Explosive Move Radar Research Boundary

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-08-21 |
| Owners | Chief Architect / Project Owner |
| Scope | Explosive Move Radar (EMR) research and advisory lane |

## Context

ATHENA needs a way to research and, only if the evidence supports it, rank NSE symbols by the historically calibrated probability of exceptional intraday expansion. The initial research focus is a positive 10% move, with configurable thresholds for 5%, 8%, 10%, 12%, 15%, and 20% events.

This is a rare-event research problem. It is not a deterministic prediction, trade signal, or order-placement capability. Building it inside the canonical ATHENA scoring pipeline would risk contaminating score, confidence, risk, Decision, and TradePlan with unvalidated evidence. It would also create leakage, survivorship-bias, corporate-action, calibration, provider-coupling, and replay risks.

ATHENA-002 freezes the canonical module map and requires an accepted ADR before a new analytical module is added. ADR-011 establishes the canonical symbol master and universe resolver that scanner-style capabilities must use.

## Decision

If accepted, ATHENA will add Explosive Move Radar as an isolated research satellite inside the modular monolith under `athena.explosive_move`.

### 1. Isolation from canonical ATHENA decisions

EMR will not contribute to or modify ATHENA scoring, confidence, risk, Decision, TradePlan, eligibility gates, or DarvaX output. It may link to existing ATHENA symbol views, but its results remain visibly experimental. Any future influence on canonical ATHENA behavior requires a separate ADR.

### 2. Read-only canonical inputs

EMR may consume canonical persisted data through explicit read-only ports: symbol identity and named-universe resolution, trading-calendar boundaries, candles, quote observations, sector/index context, market regime, and explicitly sourced catalyst evidence.

EMR business logic may not import provider clients, perform per-symbol network requests, or bypass canonical symbol resolution. Bulk ingestion remains infrastructure outside the research domain.

### 3. EMR-owned domain and persistence

EMR owns its immutable records, repositories, configuration, feature and label manifests, calibration artifacts, model metadata, scanner snapshots, and replay evidence in a separate EMR SQLite database. It may not mutate canonical ATHENA tables.

Every persisted result must record symbol and exchange, universe and as-of membership, observation and feature cutoffs, target definition, source coverage, manifest identifiers, feature/configuration/label/model versions, calibration/training cutoffs, missing-evidence states, generation time, and deterministic run ID.

### 4. Research before live ranking

The mandatory sequence is:

1. measure data availability and historical integrity;
2. build deterministic labels and a point-in-time dataset;
3. implement cutoff-safe features;
4. publish conditional base-rate research;
5. evaluate simple baselines with chronological walk-forward validation;
6. expose live scanning only after an explicit evidence gate;
7. expose UI only after the scanner contract is stable;
8. run shadow validation before any integration decision.

The first implementation milestone may conclude that ATHENA lacks sufficient history for a defensible model. That is a valid result and must be reported plainly.

### 5. Truthful labels and probability language

The event family is:

- `TOUCH_N`: session high reaches at least N% above the defined reference price;
- `CLOSE_N`: session close reaches at least N% above the defined reference price;
- `OPEN_TO_HIGH_N`: session high reaches at least N% above the session open.

Reference-price, adjustment, session, tradability, and exclusion rules must be frozen in EM-1a before labels are generated.

Outputs may be called probabilities only when calibrated on unseen chronological data and accompanied by calibration metadata. Before then, reports use `research score`, `historical frequency`, or `uncalibrated estimate`.

Any EMR `confidence` value describes the reliability and evidence coverage of the EMR estimate. It must never reuse or imply canonical ATHENA confidence.

### 6. Unknown and unavailable evidence

Missing or stale evidence is `UNKNOWN`, never zero or fabricated. Required unavailable inputs must prevent the calculation, produce explicit partial coverage, or exclude the row with a reason. A neutral substitution that affects rank requires an explicit versioned policy.

### 7. Time safety and replayability

Historical features use only information available at their declared cutoff. Labels may use later observations only as outcomes. Fitting, calibration, threshold selection, and evaluation use chronological splits. Identical source manifests, configuration, and artifacts must reproduce labels, features, ranks, and evidence.

### 8. Model promotion sequence

EMR uses the simplest defensible method first:

1. deterministic evidence score;
2. empirical conditional-frequency tables with counts and uncertainty;
3. regularized logistic baseline;
4. a tree or boosted-tree model, such as XGBoost or LightGBM, only if it materially improves unseen-period rare-event performance and calibration.

Required evaluation includes base rate, precision at useful shortlist sizes, recall, false-positive rate, lift, precision-recall AUC, Brier score, calibration error, reliability curves, MFE, MAE, time-to-target, target hit rate by probability bucket, and regime stability. In-sample accuracy cannot promote a model.

### 9. Live-state contract

If the evidence gate passes, the scanner may publish `INACTIVE`, `WATCH`, `DEVELOPING`, `CONFIRMED`, `HIGH_CONVICTION`, `FADING`, `INVALIDATED`, and `TARGET_REACHED`. EM-5 must freeze the exact transition contract before implementation. Transitions are deterministic, persisted, explainable, and versioned. They remain research observations and never authorize a trade.

### 10. Safety and scope

EMR is advisory research only. It contains no order placement, broker execution, or automatic position management. It will not claim to find a +10% mover every day. Its purpose is to test whether rare, historically supported asymmetry can be ranked better than the unconditional base rate.

## Alternatives considered

### Add EMR directly to canonical ATHENA scoring

Rejected. This would contaminate a frozen safety-sensitive pipeline with unvalidated rare-event research.

### Reuse DarvaX rankings as the EMR model

Rejected. DarvaX is independent and has no accepted evidence supporting EMR probability claims. Shared canonical market data is allowed; shared methodology or output is not.

### Build a separate network service immediately

Rejected. Distribution adds operational and replay complexity before the research proves value. A modular-monolith boundary is sufficient.

### Build the live dashboard before historical study

Rejected. A polished scanner without calibrated out-of-sample evidence would create false confidence.

### Treat missing evidence as zero

Rejected. Zero is observed; unavailable is unknown. Conflating them distorts estimates and ranks.

## Consequences

### Positive

- Experimental research cannot silently change ATHENA recommendations.
- Claims remain tied to labels, cutoffs, coverage, and replay evidence.
- Work can stop honestly if data cannot support the requested estimates.
- A later integration decision will have measurable evidence.

### Negative

- Separate persistence and provenance add implementation work.
- Point-in-time universe, corporate-action, price-band, catalyst, and long intraday history may be incomplete.
- Five to ten years of defensible coverage may require a separately approved data-source decision.
- No live scanner or UI is delivered until the evidence gate passes.

### Required controls

- Architecture tests prevent EMR imports into canonical scoring, risk, decision, and TradePlan modules.
- Coverage reports distinguish unavailable, partial, excluded, and observed evidence.
- EM-1a freezes event and adjustment contracts before label generation.
- EM-4 publishes out-of-sample calibration and shortlist utility before EM-5.
- EM-8 requires owner approval and a separate ADR for canonical integration.
