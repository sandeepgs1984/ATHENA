# ATHENA — PS-P10B Daily Chart Evidence Foundation

**Status:** Implementation complete — ready for Owner / Chief Architect review
**Date:** 2026-09-05
**Scope:** Evidence foundation only. No Portfolio Review Status, Review Guidance,
Support 1, Major Support / Exit, Target 1/2/3, numeric Review Conviction,
chart-derived Key Trigger, dashboard rendering, sync wiring, or interpretation
methodology is implemented in this milestone.

## 1. Objective

PS-P10B creates the deterministic D1 evidence foundation needed for a future
Daily Chart Portfolio Review layer. It replaces the old chart-screenshot-based
workflow with reusable, typed, point-in-time-safe evidence over canonical D1
candles.

The production direction remains:

confirmed holdings -> canonical/Kite refresh -> persisted D1 OHLCV ->
deterministic/versioned D1 evidence -> future Daily Chart Portfolio Review
methodology -> immutable Portfolio snapshot -> My Portfolio dashboard.

## 2. Architecture Boundary

Implemented in `src/athena/portfolio/daily_chart_evidence.py`.

The module is pure:

- no provider calls;
- no repository dependency;
- no clock reads;
- no dashboard code;
- no Portfolio Sync wiring;
- no PortfolioInterpreter change;
- no schema or API change;
- no mutation of existing frozen Portfolio Status, Conviction, Trend, Setup,
  Next Action, ADD, EXIT, EntryQualification, TradePlan, DecisionType, VWAP,
  RS/RVOL, or intraday trend semantics.

The future consumer must pass canonical D1 candles that were already fetched
through the approved data boundary.

## 3. Evidence Primitives

### A. SuperTrend 10,3

Added deterministic SuperTrend evidence:

- version: `supertrend-10-3-athena-v0`;
- ATR period: `10`;
- multiplier: `3`;
- ATR source: existing `athena.indicators.calculations.atr_series`;
- ATR smoothing: existing Wilder-smoothed ATR implementation;
- warm-up: requires `period + 1` D1 candles;
- completed-candle semantics: caller supplies D1 candles and `as_of`; future
  candles after `as_of` are ignored before sufficiency and calculation;
- initialization: first computable bar chooses bullish when `close >= hl2`,
  bearish otherwise;
- band carry-forward: final upper/lower bands use deterministic prior-band and
  prior-close carry-forward;
- flip semantics: latest flip is exposed as evidence only.

No claim of TradingView equivalence is made. This is ATHENA's deterministic
SuperTrend primitive. TradingView-style owner screenshots remain reference
examples only.

### B. RSI14 Review Evidence

Added typed RSI14 evidence:

- period: `14`;
- calculation source: existing `athena.indicators.calculations.rsi`;
- output: raw RSI value plus provenance;
- no review-status bands introduced.

### C. D1 Volume Evidence

Added typed volume evidence:

- latest D1 volume;
- Volume MA period: `20`;
- calculation source: existing `athena.indicators.calculations.volume_ma`;
- no expansion/compression taxonomy;
- no invented threshold.

### D. Swing / Pivot Candidate Evidence

No pivot extraction algorithm is implemented in PS-P10B.

Reason: left/right window count, confirmation delay, equal high/low handling,
point-in-time stability, and churn behavior are methodology choices. They must
be reviewed through replay before becoming a canonical primitive.

PS-P10B therefore adds typed candidate representation only:

- `StructuralLevelCandidate`;
- `StructuralLevelCandidateEvidence`;
- `StructuralLevelKind`.

The engine currently returns no candidates with
`STRUCTURAL_LEVEL_METHODOLOGY_NOT_FROZEN`.

### E. ATH / Rolling-High Relationship

Added relationship evidence that distinguishes:

- latest high/close;
- prior available-history high excluding the latest candle;
- whether the latest high exceeds that prior high;
- whether latest close is above that prior high;
- optional caller-supplied rolling-window relationship;
- whether the supplied history is fully adjusted.

No synthetic targets are generated. ATH/rolling-high evidence is not converted
into Target 1/2/3.

### F. Evidence Coherency

All evidence shares compact provenance:

- instrument id;
- timeframe (`D1`);
- `as_of`;
- accepted price timestamp;
- expected analysis timestamp;
- first/latest included D1 session;
- included candle count;
- supplied source candle count;
- evidence version.

The engine refuses incoherent evidence for wrong instrument or timeframe.
Accepted-session and expected-session mismatches are explicit reasons, not
silent stale data.

## 4. Validation

Focused runtime validation:

`rtk pytest tests/runtime/test_portfolio_daily_chart_evidence.py`

Result:

- 10 passed.

Coverage:

- SuperTrend warm-up boundary;
- deterministic rerun;
- future-D1 exclusion before calculation;
- latest SuperTrend flip evidence;
- wrong instrument and wrong timeframe incoherency;
- accepted-session mismatch;
- expected-session mismatch;
- RSI14 reuse-equivalence with existing calculation;
- volume raw/MA measurement including zero-volume behavior;
- ATH vs rolling-high relationship;
- structural-level candidate deferral;
- rolling-window parameter validation.

Static validation:

- `rtk uv run ruff check src/athena/portfolio/daily_chart_evidence.py tests/runtime/test_portfolio_daily_chart_evidence.py`
  — clean.
- `rtk uv run --no-cache mypy src/athena/portfolio/daily_chart_evidence.py`
  — clean.

Full-suite validation:

- `rtk pytest` — 3,668 passed, 0 failed, 1 skipped.

## 5. Explicit Non-Implementation

PS-P10B does not implement or populate:

- Review Status (`HOLD STRONG`, `HOLD`, `REVIEW / HOLD TIGHT`, `EXIT RISK`);
- numeric Review Conviction;
- Review Guidance prose;
- chart-derived Key Trigger;
- Support 1;
- Major Support / Exit;
- Target 1;
- Target 2;
- Target 3;
- My Portfolio dashboard changes;
- Portfolio Sync consumption;
- Portfolio snapshot schema/API changes.

Candidate Review Status labels remain candidate labels only. They are not
frozen taxonomy and are not produced by code.

## 6. Open Methodology Questions

The following must remain owner-gated:

1. Which SuperTrend compatibility target, if any, should be claimed after replay
   against owner examples. Current implementation is deterministic ATHENA
   SuperTrend, not TradingView-certified.
2. Whether Support 1 / Major Support / Exit should come from pivots, candles,
   SuperTrend bands, owner stops, or a combination.
3. Pivot confirmation delay and left/right window semantics.
4. Equal-high/equal-low handling and pivot churn tolerance.
5. Whether volume evidence gets a classification, and if so from which approved
   volume semantics.
6. Whether ATH/rolling-high relationship becomes a key trigger, target input,
   or only contextual evidence.
7. Review Guidance methodology and exact prose ownership.
8. Whether old-sheet Review Status labels are accepted as taxonomy, renamed, or
   replaced.

## 7. Milestone Review Summary

**Name.** PS-P10B Daily Chart Evidence Foundation.

**Objective.** Add deterministic, reusable D1 evidence primitives required for
future Daily Chart Portfolio Review intelligence.

**Scope completed.** SuperTrend 10,3, RSI14, Volume MA measurements,
ATH/rolling-high relationship evidence, structural-level candidate types, and
coherency/provenance contracts.

**Files created.**

- `src/athena/portfolio/daily_chart_evidence.py`
- `tests/runtime/test_portfolio_daily_chart_evidence.py`
- `docs/research/PS-P10B-DAILY-CHART-EVIDENCE-FOUNDATION.md`

**Files modified.**

- `src/athena/portfolio/__init__.py`
- `tests/api/platform/test_decision_chart_release_gate.py`
- `docs/MILESTONES.md`
- `IMPLEMENTATION_SUMMARY.md`
- `ATHENA_BRIEFING.md`

**Public APIs added.** Package exports for `DailyChartEvidenceEngine`, evidence
dataclasses, reason enums, and version/period constants.

**Tests added.** 10 focused runtime tests.

**Test results.** Focused runtime: 10 passed. Chart release-gate slice: 15
passed with the PS-P10B tests. Ruff: clean. Mypy: clean. Full suite: 3,668
passed, 0 failed, 1 skipped.

**Architecture compliance.** Compliant. Evidence-only; no schema/API/dashboard,
Portfolio Sync, PortfolioInterpreter, OpeningRangeEngine, DecisionEngine,
ScoringEngine, EntryQualification, TradePlan, or provider changes.

**Risks discovered.** TradingView equivalence is not established. Structural
levels and targets cannot honestly be produced until pivot/support/target
methodology is frozen.

**Technical debt introduced.** None. An incidental stale release-gate test
expectation was updated from dashboard asset version `9.150.0` to the already
active `9.153.0`; no dashboard source changed.

**Suggested improvements.** PS-P10C should replay candidate Daily Chart Review
methodologies against real holdings and owner examples before any snapshot or
dashboard field is populated.

**Remaining work.** Owner / Chief Architect review. PS-P10C is not authorized.

**Commit message.**

```text
feat(portfolio): add daily chart review evidence foundation

- Add PS-P10B typed D1 evidence primitives for SuperTrend 10,3, RSI14,
  Volume MA, ATH/rolling-high relationships, and structural-level candidates.
- Keep Review Status, guidance, support/exit, targets, numeric conviction, Sync,
  snapshot, schema, API, and dashboard population deferred pending owner-approved
  methodology.
- Cover warm-up, point-in-time future safety, session coherency, calculation
  reuse, candidate deferral, and deterministic replay boundaries.
```

**Ready for review.** Yes.
