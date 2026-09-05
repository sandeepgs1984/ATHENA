# PS-P10D — Daily Chart Portfolio Review Implementation

Date: 2026-09-05

Status: Implementation correction complete, ready for Owner/Chief Architect
review. PS-P10D remains not yet approved/frozen pending final owner review.

## 1. Scope

PS-P10D implements the frozen Daily Chart Portfolio Review v0 layer for My
Portfolio snapshots.

Implemented:

- `portfolio-daily-review-v0` typed Daily Review result.
- Review Status taxonomy: `HOLD_STRONG`, `HOLD`, `REVIEW_HOLD_TIGHT`, `null`.
- Primary evidence from canonical `supertrend-10-3-athena-v0`.
- Context evidence from RSI14, raw D1 volume, Volume MA20, and available-history
  high relationship.
- Deterministic guidance and reason codes.
- Snapshot/API/dashboard population through the existing My Portfolio sync
  contract.

Not implemented, by frozen owner decision:

- Support 1.
- Major Structural Support / Invalidation.
- Target 1/2/3.
- Structural Review Trigger.
- `EXIT_RISK`.
- Numeric Review Conviction.

## 2. Architecture

The new production path is:

persisted canonical D1 candles -> `DailyChartEvidenceEngine` ->
`PortfolioDailyReviewAdapter` -> typed Daily Review payload ->
Portfolio Sync immutable snapshot -> API DTO -> My Portfolio dashboard.

Daily Review remains independent from:

- Portfolio Status.
- Conviction.
- D1 Trend.
- Opening Range Setup.
- DecisionEngine.
- ScoringEngine.
- EntryQualification.
- TradePlan.
- ADD / EXIT / Next Action.
- Key Trigger.

P&L is context for guidance only. It does not determine Review Status.

RSI14 is raw context only. PS-P10D does not introduce RSI thresholds or
extended/weak classifications.

## 3. Versioning

Daily Review methodology version:

- `portfolio-daily-review-v0`

New Portfolio interpretation snapshots use:

- `portfolio-interpretation-v4`

Historical v0/v1/v2/v3 snapshots remain immutable. No backfill was performed.

## 4. Review Status Resolution

Availability/null precedence:

1. incoherent SuperTrend evidence -> `null`;
2. stale or session-mismatched SuperTrend evidence -> `null`;
3. unavailable or insufficient SuperTrend evidence -> `null`;
4. bullish SuperTrend with trailing structure intact and latest D1 high above
   prior available-history high -> `HOLD_STRONG`;
5. bullish SuperTrend with trailing structure intact -> `HOLD`;
6. bearish SuperTrend or price below trailing evidence -> `REVIEW_HOLD_TIGHT`;
7. otherwise -> `null`.

RSI, volume, VMA, available-history-high, and position P&L context do not
override the SuperTrend-driven Review Status. Unavailable RSI, volume, VMA, or
high-context evidence does not make a coherent SuperTrend review null. High
evidence is required only for `HOLD_STRONG` promotion.

## 4.1 Owner Review Correction

The owner review found two narrow issues in the first PS-P10D implementation:

- invented RSI thresholds (`>=70`, `<=40`) created unfrozen momentum context;
- unavailable/incoherent context evidence could null a valid SuperTrend-driven
  status.

Corrections applied:

- removed RSI threshold reason codes and guidance;
- retained raw RSI14 evidence only;
- made SuperTrend the only status-blocking evidence;
- allowed unavailable high evidence to fall back to `HOLD` for bullish
  SuperTrend and `REVIEW_HOLD_TIGHT` for bearish SuperTrend;
- kept high evidence as a promotion-only input for `HOLD_STRONG`.

## 5. Files

Created:

- `src/athena/portfolio/daily_review.py`
- `tests/runtime/test_portfolio_daily_review.py`

Modified:

- `src/athena/portfolio/__init__.py`
- `src/athena/portfolio/interpretation.py`
- `src/athena/portfolio/my_portfolio_contracts.py`
- `src/athena/portfolio/sync.py`
- `src/athena/api/v1/dtos/portfolio.py`
- `src/athena/api/v1/services/my_portfolio_service.py`
- `src/athena/api/static/index.html`
- `src/athena/api/static/css/05b-my-portfolio.css`
- `src/athena/api/static/js/08b-my-portfolio.js`
- `tests/api/v1/test_my_portfolio_dtos.py`
- `tests/api/v1/test_my_portfolio_import_api.py`
- `tests/api/platform/test_dashboard_hosting.py`
- `tests/api/platform/test_decision_chart_release_gate.py`

## 6. Validation

Commands run:

- `python3 -m py_compile` on changed Python files: clean.
- `node --check src/athena/api/static/js/08b-my-portfolio.js`: clean.
- `rtk pytest tests/runtime/test_portfolio_daily_review.py tests/runtime/test_portfolio_daily_chart_evidence.py tests/api/v1/test_my_portfolio_dtos.py tests/api/v1/test_my_portfolio_import_api.py tests/api/platform/test_dashboard_hosting.py tests/api/platform/test_decision_chart_release_gate.py`: 80 passed.
- `rtk uv run ruff check` on changed Python/test files: clean.
- `.venv/bin/mypy src/athena/portfolio/__init__.py src/athena/portfolio/daily_chart_evidence.py src/athena/portfolio/daily_review.py`: clean.
- `rtk pytest`: 3,675 passed, 0 failed, 1 skipped.

Direct broad mypy over `my_portfolio_service.py` still reports existing
object-typing issues in that service. The new Daily Review evidence and adapter
modules type-check cleanly.

## 7. Bounded Excel-vs-ATHENA Acceptance Comparison

Read-only comparison source:

- `db/athena.db`
- current Portfolio holdings
- persisted D1 candles
- frozen PS-P10C expected labels

Representative product comparison:

| Symbol | Old Excel review / intent | ATHENA Daily Review | ATHENA guidance | Key evidence | Owner-useful? | Known v0 limitation |
|---|---|---|---|---|---|---|
| CHENNPETRO | HOLD STRONG / protect winner; clean uptrend | HOLD | Hold while SuperTrend trailing structure remains intact; targets deferred | ST bullish, close 1450 above ST 1276.81, raw RSI14 64.52, new high false | Yes | No support/targets/structural trigger/EXIT_RISK/numeric conviction |
| AZAD | HOLD STRONG; ATH/blue-sky winner | HOLD | Hold while SuperTrend trailing structure remains intact; targets deferred | ST bullish, close 2781 above ST 2562.85, raw RSI14 58.33, new high false; reference symbol not in current holdings | Yes for chart-health; not a current holding row | Same v0 structural deferrals |
| JINDWORLD | Powerful breakout; ride while structure holds | HOLD | Hold while SuperTrend trailing structure remains intact; targets deferred | ST bullish, close 57.78 above ST 43.01, raw RSI14 83.72, new high false | Yes | Same v0 structural deferrals |
| RAINBOW | Weakening / below SuperTrend; tighter review | REVIEW_HOLD_TIGHT | Review closely while bearish SuperTrend evidence persists; support methodology deferred | ST bearish, close 1445 below ST 1541.77, raw RSI14 46.25 | Yes | Same v0 structural deferrals |
| RATNAVEER | Breakout / momentum; not in current holdings | HOLD | Hold while SuperTrend trailing structure remains intact; targets deferred | ST bullish, close 308.25 above ST 255.59, raw RSI14 74.58; reference symbol not in current holdings | Yes for chart-health; not a current holding row | Same v0 structural deferrals |
| HBLENGINE | Weak/damaged holding | REVIEW_HOLD_TIGHT | Review closely while bearish SuperTrend evidence persists; loss alone does not create EXIT_RISK | ST bearish, close 695 below ST 714.13, raw RSI14 50.76, loss context | Yes | Same v0 structural deferrals |

Recommendation: ACCEPT.

Missing deferred structural levels are not a rejection reason because
PS-P10C.1 explicitly froze them as NO-GO for v0.

ATHENA now automatically answers the v0-safe product questions:

- current D1 chart-health state from canonical SuperTrend;
- whether the holding is structurally healthy or deserves tighter review;
- why, with raw evidence and reason codes;
- what the owner should pay attention to within frozen methodology limits;
- this can be generated from persisted D1 data without another chart screenshot.

## 8. Milestone Review Summary

Objective: replace the empty My Portfolio daily-chart review experience with
the owner-approved v0 review layer generated from persisted D1 evidence.

Scope completed: Daily Review adapter, Sync wiring, snapshot/API DTO
serialization, dashboard columns, tests, and documentation.

Public APIs added: Daily Review package exports and nullable API row payload.

Schema changes: none.

Architecture compliance: pass.

ADR impact: none.

Risks: Excel parity is intentionally partial until a future owner-authorized
structural-level methodology exists.

Remaining work: Owner/Chief Architect review. PS-P10E is not authorized.

Proposed commit message:

```text
feat(portfolio): add Daily Chart Review adapter

- Add portfolio-daily-review-v0 as a separate My Portfolio review layer so
  persisted D1 evidence can populate Excel-like review status and guidance.
- Wire SuperTrend 10,3, RSI14, volume/VMA, and available-history-high evidence
  into Portfolio Sync snapshots with typed API provenance.
- Render Daily Review and Daily Guidance in the My Portfolio dashboard while
  keeping structural support, targets, EXIT_RISK, and numeric Review Conviction
  deferred for v0.
- Preserve existing Status, Conviction, Trend, Setup, Decision, Entry
  Qualification, TradePlan, ADD, EXIT, and Next Action semantics.
```
