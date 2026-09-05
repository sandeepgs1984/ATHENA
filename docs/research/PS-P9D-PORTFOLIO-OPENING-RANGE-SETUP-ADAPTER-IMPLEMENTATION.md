# ATHENA Portfolio Sync - PS-P9D Opening-Range Setup Adapter Implementation

**Date:** 2026-09-05
**Branch:** `feature/portfolio-sync`
**Milestone:** PS-P9D - implementation
**Status:** Owner / Chief Architect approved and frozen 2026-09-05

---

## 1. Objective

Implement only the PS-P9C-frozen L1 Opening Range Setup methodology for My
Portfolio without changing architecture, schema, APIs, OpeningRangeEngine,
EntryQualification, Trend, Status, Action, Conviction, TradePlan, or broker
behavior.

## 2. Scope Completed

Implemented `src/athena/portfolio/setup_adapter.py` as a thin adapter from
persisted canonical M5 evidence through the existing `OpeningRangeEngine` into
typed Portfolio Setup evidence.

## 3. Frozen Labels

Owner-facing Setup labels are exactly `BREAKOUT`, `BREAKDOWN`, or null. There
is no owner-facing `UNKNOWN`.

## 4. L1 Rule

Setup emits `BREAKOUT` only when OR15 and OR30 are both `COMPLETE`, both have
active `UPSIDE_BREAKOUT_EVENT`, and neither returned inside range. It emits
`BREAKDOWN` only for the corresponding active `DOWNSIDE_BREAKDOWN_EVENT`
agreement.

## 5. Null Precedence

The adapter applies the PS-P9C frozen null precedence:
`SETUP_EVIDENCE_INCOHERENT`, `SETUP_EVIDENCE_STALE`,
`SETUP_EVIDENCE_UNAVAILABLE`, `SETUP_OR_INCOMPLETE`,
`SETUP_OR_WINDOWS_CONFLICT`, `SETUP_RETURNED_INSIDE_RANGE`,
`SETUP_SINGLE_WINDOW_ONLY`, then `SETUP_NOT_PRESENT`.

## 6. Engine Reuse

The adapter delegates OR15/OR30 formation, relation, breakout events,
returned-inside behavior, and canonical-slot filtering to the real
`OpeningRangeEngine`.

## 7. Future Protection

The adapter filters at the analysis boundary and relies on completed-candle
semantics so future M5 candles do not affect classification.

## 8. Evidence Coherence

Setup evidence records instrument, session, analysis/evidence as-of, latest
completed M5 slot, OR15 status/event/returned-inside/first-event timestamp, and
OR30 status/event/returned-inside/first-event timestamp.

## 9. Sync Wiring

Portfolio Sync resolves Setup evidence alongside Trend evidence and passes it
as typed input to the pure `PortfolioInterpreter`.

## 10. Interpreter Version

New Portfolio interpretations are versioned `portfolio-interpretation-v3`.
Existing v0/v1/v2 snapshots are not backfilled.

## 11. Combined Field

The existing `trend_setup` domain field and `trend_or_setup` DTO/API alias are
reused. Rendered examples include `UPTREND / BREAKOUT`, `DOWNTREND /
BREAKDOWN`, `MIXED / -`, and `UPTREND / -`.

## 12. Independence

Setup does not affect Status, Next Action, ADD, EXIT, Conviction, Key Trigger,
Major Support / Exit, Support 1, Target 1, Target 2/3, D1 Trend, Decision, or
EntryQualification.

## 13. Dashboard

The My Portfolio dashboard reason summary recognizes the new Setup reason
codes. No column shape or endpoint route changed.

## 14. Public APIs Added

No new API endpoints, request bodies, response fields, or database columns were
added.

## 15. Schema

No schema migration was added. Existing immutable snapshot/provenance payloads
carry the new evidence detail.

## 16. Files Created

- `src/athena/portfolio/setup_adapter.py`
- `tests/runtime/test_portfolio_setup_adapter.py`
- `docs/research/PS-P9D-PORTFOLIO-OPENING-RANGE-SETUP-ADAPTER-IMPLEMENTATION.md`

## 17. Files Modified

- `src/athena/portfolio/interpretation.py`
- `src/athena/portfolio/sync.py`
- `src/athena/api/static/js/08b-my-portfolio.js`
- `tests/runtime/test_portfolio_interpretation.py`
- `tests/api/v1/test_my_portfolio_import_api.py`
- `tests/api/platform/test_dashboard_hosting.py`
- `docs/research/PS-P9C-PORTFOLIO-OPENING-RANGE-SETUP-LIFECYCLE-FREEZE.md`
- `docs/MILESTONES.md`
- `IMPLEMENTATION_SUMMARY.md`
- `ATHENA_BRIEFING.md`

## 18. Tests Added

Added adapter coverage for L1 labels, deterministic null precedence, incoherent
OR context, future M5 protection, stale evidence, and unavailable evidence.

## 19. Tests Updated

Updated interpreter and My Portfolio sync/dashboard tests for
`portfolio-interpretation-v3`, combined Trend / Setup rendering, setup
provenance, and setup non-interference.

## 20. Focused Validation

`rtk pytest tests/runtime/test_portfolio_setup_adapter.py
tests/runtime/test_portfolio_interpretation.py`: 36 passed.

## 21. API Validation

`rtk pytest tests/api/v1/test_my_portfolio_import_api.py
tests/api/v1/test_my_portfolio_dtos.py
tests/api/platform/test_dashboard_hosting.py`: 58 passed.

## 22. Remaining Validation

`rtk uv run ruff check` on changed Python files: all checks passed.

`.venv/bin/mypy src/athena/portfolio/setup_adapter.py
src/athena/portfolio/interpretation.py src/athena/portfolio/sync.py`: success,
no issues found in 3 source files.

`rtk pytest`: 3,658 passed, 1 skipped.

`rtk git diff --check`: clean.

Final changed-file check confirms `uv.lock`, schema files, `OpeningRangeEngine`,
and EntryQualification files are untouched.

## 23. Architecture Compliance

The implementation preserves provider independence, deterministic pure
classification, immutable snapshots, explicit provenance, and the advisory-only
boundary.

## 24. ADR Compliance

No ADR change is required. PS-P9D uses existing architecture and frozen
contracts.

## 25. OpeningRangeEngine

`OpeningRangeEngine` is unchanged.

## 26. EntryQualification

EntryQualification models, persistence, and Decision wiring are unchanged.

## 27. Decision and Scoring

DecisionEngine and ScoringEngine are unchanged.

## 28. Broker and Orders

No order placement or broker behavior was added.

## 29. uv.lock

`uv.lock` is intended to remain untouched by PS-P9D.

## 30. Risks

When no current-session M5 rows exist, Setup nulls as `SETUP_OR_INCOMPLETE`
because OR15/OR30 cannot be complete. This is expected under the frozen L1
precedence.

## 31. Technical Debt

Support 1, Target 2/3, REDUCE, ROTATE, allocation, ranking, and history remain
deferred.

## 32. Suggested Improvements

After owner review, consider a production observation pass over real current
Portfolio holdings to characterize label frequency without changing thresholds
or methodology.

## 33. Remaining Work

Wait for Owner direction for the next Portfolio milestone. Do not start PS-P10
or another Portfolio Intelligence methodology automatically.

## 34. Phase Outcome

PS-P9D is Owner / Chief Architect approved and frozen 2026-09-05.

## 35. Suggested Commit Message

```text
feat(portfolio): add Opening Range Setup adapter

- Freeze PS-P9C null precedence and owner-approved L1 Setup lifecycle.
- Add a Portfolio Setup adapter that delegates OR15/OR30 evidence to OpeningRangeEngine.
- Wire typed Setup evidence into Portfolio Sync and interpretation-v3 snapshots.
- Reuse trend_or_setup for combined Trend / Setup rendering without schema changes.
- Cover L1 labels, null precedence, future-M5 safety, sync provenance, and dashboard reasons.
```
