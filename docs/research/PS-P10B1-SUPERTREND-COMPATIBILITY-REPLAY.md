# ATHENA — PS-P10B.1 SuperTrend 10,3 Compatibility / Replay Validation

**Status:** Owner / Chief Architect approved and closed
**Date:** 2026-09-05
**Scope:** Research/validation only. No Portfolio Review methodology, Portfolio
field population, SuperTrend formula change, schema/API change, Sync wiring, or
dashboard source change.

## 1. Owner Decision Context

PS-P10B was conditionally approved after source review. Architecture and
evidence-only scope were accepted, with one required follow-up before freezing:
validate whether the current `supertrend-10-3-athena-v0` primitive behaves close
enough to the owner's previous Daily Chart workflow to become canonical PS-P10
evidence.

Owner / Chief Architect approved this validation and froze
`supertrend-10-3-athena-v0` as the canonical PS-P10 Daily Chart Review
SuperTrend evidence primitive on 2026-09-05. TradingView equivalence is not
claimed. PS-P10C remains not started and unauthorized.

## 2. Implementation Audit

Audited implementation: `src/athena/portfolio/daily_chart_evidence.py`

Frozen facts observed:

| Item | Implementation |
|---|---|
| Version | `supertrend-10-3-athena-v0` |
| ATR period | `10` |
| Multiplier | `3` |
| ATR source | Existing `athena.indicators.calculations.atr_series` |
| ATR semantics | Wilder-smoothed ATR, seeded from the first 10 true ranges |
| First computable index | Candle index `10` zero-based, requiring `period + 1` candles |
| Basic upper band | `hl2 + multiplier * atr` |
| Basic lower band | `hl2 - multiplier * atr` |
| Initial direction | `BULLISH` when `close >= hl2`, else `BEARISH` |
| Final upper carry-forward | Current basic upper replaces previous final upper only when it is lower, or when prior close was above prior final upper |
| Final lower carry-forward | Current basic lower replaces previous final lower only when it is higher, or when prior close was below prior final lower |
| Bullish -> bearish flip | Latest close `< final_lower_band` |
| Bearish -> bullish flip | Latest close `> final_upper_band` |
| Equality behavior | Equality does not flip. Bullish holds at `close == final_lower_band`; bearish holds at `close == final_upper_band`; initialization equality is bullish |
| Warm-up boundary | `10` candles unavailable, `11` candles computable |
| Point-in-time behavior | Candles after `as_of` session are filtered before sufficiency and calculation |

No implementation rule was modified during this audit.

## 3. Real-Data Replay Setup

Source database: `db/athena.db`

Replay cutoff: `2026-09-04T00:00:00+05:30`

Representative persisted D1 histories:

- `NSE:CHENNPETRO`
- `NSE:JINDWORLD`
- `NSE:RAINBOW`
- `NSE:RATNAVEER`
- `NSE:AZAD` as a strong near-ATH winner
- `NSE:TARIL` as a damaged/downtrend holding
- `NSE:HBLENGINE` as a damaged/downtrend holding

All selected histories have persisted D1 candles through `2026-09-04`. All
selected histories are stored as unadjusted (`adjusted = 0` on every checked
D1 candle), so compatibility is characterized against raw persisted history,
not adjusted chart history.

## 4. Latest Reference Comparison

Owner chart screenshots provide visible reference values for four symbols.
Those references are screenshot-level values, not exact machine-readable
exports, so every comparison below is classified as
`APPROXIMATE_VISUAL_COMPARISON`.

| Symbol | Sessions | Persisted latest close | ATHENA direction | ATHENA ST | Screenshot direction | Screenshot ST | Direction agreement | Level delta | Level delta % | Classification |
|---|---:|---:|---|---:|---|---:|---|---:|---:|---|
| `NSE:CHENNPETRO` | 759 | 1450.00 | BULLISH | 1276.8050 | BULLISH | 1274.54 | Yes | +2.2650 | 0.18% | APPROXIMATE_VISUAL_COMPARISON |
| `NSE:JINDWORLD` | 759 | 57.78 | BULLISH | 43.0082 | BULLISH | 42.93 | Yes | +0.0782 | 0.18% | APPROXIMATE_VISUAL_COMPARISON |
| `NSE:RAINBOW` | 759 | 1445.00 | BEARISH | 1541.7730 | BEARISH | 1541.95 | Yes | -0.1770 | 0.01% | APPROXIMATE_VISUAL_COMPARISON |
| `NSE:RATNAVEER` | 741 | 308.25 | BULLISH | 255.5884 | BULLISH | 259.88 | Yes | -4.2916 | 1.65% | APPROXIMATE_VISUAL_COMPARISON |

The persisted latest closes also differ slightly from the screenshot closes:

- CHENNPETRO screenshot: 1452.20; persisted: 1450.00.
- JINDWORLD screenshot: 57.51; persisted: 57.78.
- RAINBOW screenshot: 1447.20; persisted: 1445.00.
- RATNAVEER screenshot: 304.75; persisted: 308.25.

This makes exact-value attribution impossible from screenshots. No
direction-level divergence was observed.

## 5. Cross-Section Replay Results

| Symbol | Sessions checked | Latest direction | Latest ST | Latest ATR | Historical flips | First observed flip | Deterministic rerun | Future-leakage check |
|---|---:|---|---:|---:|---:|---|---|---|
| `NSE:CHENNPETRO` | 759 | BULLISH | 1276.8050 | 55.9650 | 21 | 2023-09-08 BEARISH -> BULLISH | Pass | Pass |
| `NSE:JINDWORLD` | 759 | BULLISH | 43.0082 | 3.4639 | 15 | 2024-02-06 BEARISH -> BULLISH | Pass | Pass |
| `NSE:RAINBOW` | 759 | BEARISH | 1541.7730 | 36.4667 | 13 | 2023-11-07 BULLISH -> BEARISH | Pass | Pass |
| `NSE:RATNAVEER` | 741 | BULLISH | 255.5884 | 17.7635 | 17 | 2023-10-13 BEARISH -> BULLISH | Pass | Pass |
| `NSE:AZAD` | 668 | BULLISH | 2562.8519 | 101.1393 | 15 | 2024-01-30 BEARISH -> BULLISH | Pass | Pass |
| `NSE:TARIL` | 759 | BEARISH | 313.8006 | 9.4549 | 20 | 2023-09-08 BEARISH -> BULLISH | Pass | Pass |
| `NSE:HBLENGINE` | 759 | BEARISH | 714.1331 | 22.4849 | 18 | 2023-10-06 BEARISH -> BULLISH | Pass | Pass |

Total latest-symbol checks: 7.

Total historical point-in-time computable sessions replayed:

- CHENNPETRO: 749
- JINDWORLD: 749
- RAINBOW: 749
- RATNAVEER: 731
- AZAD: 658
- TARIL: 749
- HBLENGINE: 749
- Total: 5,134

Total historical SuperTrend flips observed: 119.

The future-leakage check appended an artificial future D1 candle after the
`as_of` session and verified that direction, SuperTrend, final bands, and ATR
were unchanged.

## 6. Divergence Analysis

No direction divergence was found against available owner references.

No exact-value comparison was possible because the references are screenshots,
not exported indicator values. Latest level differences were small in the three
cleanest screenshot comparisons and widest for RATNAVEER.

Likely sources of residual level difference:

- screenshot values are visual/read-off references, not exact exports;
- persisted D1 closes differ from the screenshot closes;
- all checked ATHENA histories are unadjusted, while the charting source may
  apply vendor/session/corporate-action handling not encoded in the screenshot;
- TradingView equivalence is not claimed and cannot be proven from screenshots.

No evidence points to a material bug in ATR period, ATR seeding, initialization,
band carry-forward, flip boundary, equality behavior, warm-up handling, or
future-candle filtering.

First divergence session: none observed for direction. Exact-value divergence
cannot be established from approximate visual references.

## 7. Incidental Release-Gate Test Confirmation

The PS-P10B implementation changed one stale test expectation in
`tests/api/platform/test_decision_chart_release_gate.py` from dashboard asset
version `9.150.0` to `9.153.0`.

Confirmed: no dashboard source/version was changed by PS-P10B or PS-P10B.1.
The active dashboard HTML already referenced `9.153.0`; the test was stale.

## 8. Validation Results

Commands run:

- `rtk pytest tests/runtime/test_portfolio_daily_chart_evidence.py`
  - 10 passed.
- `rtk pytest tests/runtime/test_portfolio_daily_chart_evidence.py tests/api/platform/test_decision_chart_release_gate.py`
  - 15 passed.
- `rtk uv run ruff check src/athena/portfolio/__init__.py src/athena/portfolio/daily_chart_evidence.py tests/runtime/test_portfolio_daily_chart_evidence.py tests/api/platform/test_decision_chart_release_gate.py`
  - clean.
- `rtk uv run --no-cache mypy src/athena/portfolio/__init__.py src/athena/portfolio/daily_chart_evidence.py`
  - clean.
- `rtk pytest`
  - 3,668 passed, 0 failed, 1 skipped.

Validation script was read-only against `db/athena.db`. It created no production
rows and triggered no provider calls.

## 9. Owner Decision

Owner accepted recommendation **A. FREEZE `supertrend-10-3-athena-v0` as
canonical PS-P10 evidence.**

Reason: the implementation is deterministic, point-in-time safe, has explicit
warm-up/equality/session semantics, replayed cleanly across 5,134 historical
point-in-time sessions and 119 observed flips, and agrees directionally with all
available owner screenshot references. Approximate level differences are
consistent with screenshot/source precision limitations and do not justify a
formula change.

This decision does not claim TradingView equivalence. ATHENA's explicitly
versioned primitive is frozen as the canonical Portfolio Review evidence source.

## 10. Milestone Review Summary

**Name.** PS-P10B.1 SuperTrend 10,3 Compatibility / Replay Validation.

**Objective.** Validate the conditionally approved PS-P10B SuperTrend primitive
before PS-P10B freeze.

**Scope completed.** Implementation audit, representative owner-holding replay,
approximate screenshot comparison, historical flip replay, deterministic rerun,
future-leakage check, adjusted/unadjusted observation, and recommendation.

**Files created.**

- `docs/research/PS-P10B1-SUPERTREND-COMPATIBILITY-REPLAY.md`

**Files modified.**

- `docs/MILESTONES.md`
- `IMPLEMENTATION_SUMMARY.md`
- `ATHENA_BRIEFING.md`

**Public APIs added.** None.

**Tests added.** None. Validation/research only.

**Test results.** Full suite from PS-P10B remains green: 3,668 passed, 0 failed,
1 skipped. No production code changed in PS-P10B.1.

**Architecture compliance.** Compliant. No formula, Sync, PortfolioInterpreter,
schema/API/dashboard, provider, Decision, Scoring, EntryQualification, or
TradePlan change.

**Risks discovered.** Exact TradingView equivalence remains unproven because
only screenshots, not exported indicator values, are available.

**Technical debt introduced.** None.

**Suggested improvements.** If the owner wants TradingView equivalence claimed
later, capture exact exported SuperTrend values for a small reference set and
compare against this primitive without changing Portfolio methodology.

**Remaining work.** PS-P10C is not started and remains unauthorized.

**Commit message.**

```text
docs(portfolio): validate PS-P10B SuperTrend compatibility

- Record PS-P10B conditional approval and complete the required PS-P10B.1
  SuperTrend 10,3 replay audit before freeze.
- Compare ATHENA's versioned SuperTrend evidence against persisted D1 histories
  and owner screenshot references without changing the formula or populating
  Portfolio Review fields.
- Recommend freezing supertrend-10-3-athena-v0 as canonical PS-P10 evidence
  while keeping TradingView equivalence unclaimed.
```

**Ready for review.** No further PS-P10B.1 review pending; Owner / Chief
Architect approved/closed 2026-09-05.
