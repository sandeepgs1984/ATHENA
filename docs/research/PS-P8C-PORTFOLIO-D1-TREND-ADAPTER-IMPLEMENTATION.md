# ATHENA Portfolio Sync - PS-P8C D1 Trend Adapter Implementation

**Date:** 2026-09-04
**Branch:** `feature/portfolio-sync`
**Milestone:** PS-P8C - implementation only
**Status:** Owner / Chief Architect approved and frozen 2026-09-04

---

## 1. Executive Summary

PS-P8C implements the owner-approved PS-P8B D1 Trend methodology and nothing
else. My Portfolio now derives a holding-level Trend from that holding's own
coherent D1 candles using the approved SMA20/SMA50 structure rule:

- `UPTREND`
- `DOWNTREND`
- `MIXED`
- `null` when D1 evidence is unavailable or incoherent

Setup remains intentionally deferred and unavailable. No support, target,
ranking, allocation, reduce, rotate, history, broker, order, or new schema
behavior was added.

Final Owner/Chief Architect review found one local hardening gap: direct
`classify_candles()` callers could supply a future D1 candle even though the
normal repository-backed `resolve()` path already queried with an `as_of`
cutoff. The correction now enforces no-future-evidence semantics inside the
adapter boundary itself before sufficiency counting, latest-candle selection,
SMA calculation, and classification.

## 2. Frozen Owner Decisions Implemented

- Candidate B is implemented.
- `UPTREND`, `DOWNTREND`, `MIXED`, and `null` are the only Trend outcomes.
- `SIDEWAYS` and `UNKNOWN` are not Portfolio Trend values.
- D1 Trend is derived from instrument D1 candles only.
- Regime SMA20/SMA50 periods are reused from `config/regime.json`.
- Market Regime labels are not consumed directly.
- Intraday, EntryQualification, Relative Strength, Decision, TradePlan,
  Conviction, DarvaX, and EMR do not classify Trend.
- Setup remains deferred with `SETUP_METHODOLOGY_DEFERRED`.
- New snapshots use `portfolio-interpretation-v2`.
- Existing snapshot schema is reused; no backfill is performed.

## 3. Adapter Architecture

`PortfolioTrendAdapter` owns Portfolio Trend evidence resolution. It reads up to
50 persisted D1 candles for the holding's canonical instrument in `resolve()`,
validates exact session coherency, computes SMA20/SMA50 using the approved
Regime periods, and returns typed `PortfolioTrendEvidence`.

`classify_candles()` also protects the adapter boundary for direct callers: it
filters supplied candles to D1 sessions not after the cutoff session
(`expected_analysis_as_of` when supplied, otherwise `accepted_price_as_of`),
sorts the allowed candles, validates instrument/timeframe, requires at least 50
usable candles after exclusion, trims to the latest 50 usable candles, and only
then calculates SMA20/SMA50.

The pure `PortfolioInterpreter` receives only typed evidence. It performs no
repository access, provider access, indicator engine calls, scoring calls,
DecisionEngine calls, or raw candle loading.

## 4. Classification Formula

- `UPTREND`: SMA20 > SMA50 and latest coherent D1 close >= SMA50.
- `DOWNTREND`: SMA20 < SMA50 and latest coherent D1 close <= SMA50.
- `MIXED`: at least 50 coherent D1 candles and neither directional condition
  holds.
- `null`: evidence unavailable, insufficient, mismatched, stale, or incoherent.

## 5. Coherency Contract

Trend is coherent only when:

- every candle belongs to the holding instrument;
- every candle is D1;
- at least 50 candles are available through the expected analysis cutoff;
- evidence count is evaluated only after future-session candles are excluded;
- latest Trend candle session equals the accepted Portfolio price session;
- latest Trend candle session equals the expected analysis session when supplied;
- no previous-session fallback is used for Trend;
- no future candle can influence either direct classification or repository
  resolution.

If Trend is unavailable or incoherent, Portfolio Sync still succeeds for the row
when the row's required valuation inputs are usable.

## 6. Snapshot / API Behavior

The existing `trend_setup` domain field and `trend_or_setup` DTO/API field are
reused. They now contain only the Trend dimension:

- `UPTREND`
- `DOWNTREND`
- `MIXED`
- `null`

Setup is not encoded in this field. Dashboard display shows the Trend label or
`-` with reason-code tooltip text.

## 7. Reason Codes

PS-P8C uses the frozen reason-code vocabulary:

- `TREND_UP_FROM_D1_SMA_STRUCTURE`
- `TREND_DOWN_FROM_D1_SMA_STRUCTURE`
- `TREND_MIXED_FROM_D1_SMA_STRUCTURE`
- `TREND_D1_EVIDENCE_UNAVAILABLE`
- `TREND_D1_EVIDENCE_INCOHERENT`
- `SETUP_METHODOLOGY_DEFERRED`

## 8. Provenance

Portfolio snapshot provenance records compact Trend evidence:

- label
- reason
- D1 session
- SMA20 period/value
- SMA50 period/value
- latest close
- candles used
- coherency flag

No raw candle history is duplicated into the snapshot row.

## 9. Tests Added

Added focused coverage for:

- UPTREND and DOWNTREND boundary equality against SMA50;
- MIXED when SMA and close structure disagree or SMAs are equal;
- 49-candle unavailable and 50-candle classification boundary;
- direct `classify_candles()` exclusion of 49 valid candles plus one future
  candle as unavailable with `candles_used=49`;
- direct `classify_candles()` equality between 50 valid candles and 50 valid
  candles plus one future candle;
- repository resolution ignoring future candles beyond expected session;
- exact accepted/expected-session coherency;
- wrong instrument and wrong timeframe incoherency;
- deterministic identical-input classification;
- interpreter Trend mapping without Status/Action/TradePlan changes;
- incoherent Trend null behavior;
- ADD and EXIT independence from Trend;
- Sync population of the existing Trend / Setup field;
- Sync null behavior for prior-session Trend evidence;
- currentness regressions via the existing PS-P6B tests;
- dashboard tooltip/reason-code contract and no Portfolio `SIDEWAYS` label.

## 10. Explicit Non-Changes

- No Setup methodology.
- No Support 1 methodology.
- No Target 2/3 methodology.
- No REDUCE or ROTATE.
- No allocation, ranking, or portfolio-level advisor.
- No broker or order placement behavior.
- No new table, migration, DTO field, or API route.
- No historical backfill.
- No market Regime direct reuse.
- No ScoringEngine, DecisionEngine, Risk, or Confidence methodology change.

## 11. Files Changed

Created:

- `src/athena/portfolio/trend_adapter.py`
- `tests/runtime/test_portfolio_trend_adapter.py`
- `docs/research/PS-P8C-PORTFOLIO-D1-TREND-ADAPTER-IMPLEMENTATION.md`

Modified:

- `src/athena/portfolio/__init__.py`
- `src/athena/portfolio/interpretation.py`
- `src/athena/portfolio/sync.py`
- `src/athena/api/v1/services/my_portfolio_service.py`
- `src/athena/api/static/js/08b-my-portfolio.js`
- `tests/runtime/test_portfolio_interpretation.py`
- `tests/api/v1/test_my_portfolio_import_api.py`
- `tests/api/platform/test_dashboard_hosting.py`
- `docs/research/PS-P8B-PORTFOLIO-D1-TREND-METHODOLOGY-FREEZE.md`
- `docs/MILESTONES.md`
- `ATHENA_BRIEFING.md`
- `IMPLEMENTATION_SUMMARY.md`

## 12. Validation

Direct Trend adapter unit tests after final-review correction: `11 passed`.

Focused PS-P8C/My Portfolio slice: `88 passed`.

Focused PS-P8C/My Portfolio plus file-backed smoke slice: `91 passed`.

Full repository suite: `3380 passed, 0 failed, 1 skipped`.

File-backed daily smoke script: PASS.

Touched-file Ruff: clean.

`git diff --check`: clean.

Core Portfolio mypy (`trend_adapter.py`, `interpretation.py`, `sync.py`):
clean. Direct `.venv/bin/mypy` was used because sandboxed `uv run mypy` cannot
open the user-level uv cache in this environment. Strict mypy over
`my_portfolio_service.py` still reports pre-existing service DTO typing debt
outside PS-P8C.

## 13. Known Limitations

Trend is available only when 50 coherent D1 candles are persisted for the
holding and the latest D1 Trend session exactly matches the accepted Portfolio
price and expected analysis sessions. This strictness is intentional per PS-P8B.

Setup remains unavailable by design.

## 14. Milestone Outcome

PS-P8C is Owner / Chief Architect approved and frozen as of 2026-09-04 after
the final future-evidence hardening correction. Portfolio Intelligence V2 now
includes Conviction and D1 Trend only. Setup, Support, Target, REDUCE, ROTATE,
allocation, ranking, and history remain deferred until separate owner-approved
milestones.

## 15. Suggested Commit Message

```text
feat(portfolio): add D1 Trend adapter

- Implement PS-P8C D1 Trend from coherent holding D1 candles using the frozen
  SMA20/SMA50 Candidate B methodology.
- Populate only the existing Trend / Setup field with UPTREND, DOWNTREND, or
  MIXED and keep Setup explicitly deferred.
- Bump new Portfolio interpretation output to portfolio-interpretation-v2 while
  preserving Status, ADD, EXIT, Conviction, currentness, schema, and history.
```
