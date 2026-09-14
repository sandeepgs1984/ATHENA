# SI-P2C — Completed-D1 Chart Intelligence Discovery

Status: **DISCOVERY COMPLETE — IMPLEMENTATION AUTHORIZED**

Date: 2026-09-13

Scope: SI-P2C only. SI-P1, SI-P2A, and SI-P2B remain frozen.

## 1. Discovery verdict

**GO without an ADR or frozen-contract change.** The existing Stock 360 chart
can gain completed-D1 SMA20/SMA50 series, exact structural zones, approved
targets, a completed-close marker, deterministic label collision avoidance,
and compact inspection using its existing single candle request and the
existing SI-P1 bundle.

The chart remains a presentation concern. It does not create a trend verdict,
level, signal, recommendation, prediction, or score. No composer, DTO,
hydration, provider, DecisionEngine, Portfolio Sync, or DarvaX behavior needs
to change.

## 2. Architecture traced

1. `siChartBlock()` in `08c-symbol-intelligence.js` owns the Stock 360 chart
   host and completed-D1 disclosure.
2. `renderSymbolIntelligence()` mounts the host only for a resolved identity
   with present D1 evidence, preserving the P2B invalid/unavailable behavior.
3. `loadSiD1Chart()` performs one read-only request to the existing endpoint:
   `GET /api/v1/market/instruments/{id}/candles?timeframe=1d&limit=180`.
4. The market router delegates to `MarketHistoryService.recent_candles()`.
   `SqliteCandleHistoryProvider` reads `SqliteRepository.list_candles_recent()`;
   the payload is chronological provider-independent OHLCV plus an existing
   generic moving-average field.
5. The SI composer separately reads up to 300 persisted D1 candles and passes
   them to `SymbolIntelligenceD1Adapter`. Its injected
   `PortfolioTrendAdapter` owns the approved SMA20/SMA50 values and textual
   `UPTREND` / `DOWNTREND` / `MIXED` result. The adapter uses the pure
   `athena.indicators.calculations.sma()` arithmetic mean and only the final 50
   eligible candles.
6. The same D1 adapter invokes `PortfolioStructuralReviewEngine` and exposes
   Support 1, Major Support, Review Trigger, and Target 1–3 as typed zones with
   `PORTFOLIO_STRUCTURAL_REVIEW` lineage.
7. The existing SVG renderer uses fixed dimensions with a responsive
   `viewBox`, draws candles and volume, and currently draws only the `upper`
   boundary of S1/MS and `lower` boundary of RT as single dashed lines.
8. The Decision chart is a richer custom SVG implementation, but it is
   intraday and TradePlan-specific. Its generic formatting/inspection ideas
   are reusable; its plan overlays, preferences, event markers, and freshness
   semantics are not.

This is compatible with ATHENA-002's presentation boundary: the dashboard
renders read-only stored evidence and does not become an analytical engine.

## 3. Completed-D1 and coherence boundary

The chart request and SI bundle both read the canonical SQLite D1 ledger, but
they are separate reads and the generic market-history endpoint does not own
SI's completed-session meaning. Therefore P2C must:

- treat `d1.latest_session` as the authoritative frozen SI completed-D1 cutoff;
- sort the chart payload chronologically and retain only valid D1 rows whose
  market-date is at or before that cutoff;
- exclude later rows as future/current-session rows for this chart;
- compute each trailing SMA only after 20/50 valid closes;
- compare final calculated SMA20/SMA50 with `d1.fast_sma`/`d1.slow_sma` using
  display precision (two decimals);
- fail the SMA overlay closed with explicit `COHERENCE UNAVAILABLE` copy if the
  final values differ, rather than displaying two truths.

The frontend is the correct calculation layer for the plotted *series* because
it already receives the exact completed-D1 candle sequence, the operation is a
pure deterministic visualization, and adding series to the frozen SI DTO or
generic market API would expand a contract unnecessarily. The authoritative
latest values and textual trend remain backend-owned.

## 4. Discovery classification matrix

| Proposed element | Class | Decision / evidence owner |
|---|---|---|
| OHLC candles | EXISTING | Canonical persisted D1 candle payload; render valid rows through the SI cutoff |
| Volume | EXISTING | Existing D1 candle payload; retain candle-direction colors only |
| SMA20 | DERIVED_SAFE | Plot arithmetic mean of each trailing 20 valid closes; reconcile final value to `d1.fast_sma` |
| SMA50 | DERIVED_SAFE | Plot arithmetic mean of each trailing 50 valid closes; reconcile final value to `d1.slow_sma` |
| Completed-D1 close marker | PRESENTATION_ONLY | Exact final accepted candle close, reconciled to `d1.close` |
| Support 1 | EXISTING | `d1.support_1`, structural-review lineage |
| Major Support | EXISTING | `d1.major_support`, structural-review lineage |
| Review Trigger | EXISTING | `d1.review_trigger`, structural-review lineage |
| Target 1 | EXISTING | `d1.target_1`, structural-review lineage |
| Target 2 | EXISTING | `d1.target_2`; render only when non-empty and coherent |
| Target 3 | EXISTING | `d1.target_3`; render only when non-empty and coherent |
| Available-history high | OUT_OF_SCOPE | Existing fact, deliberately excluded to limit clutter; Price Map remains authoritative |
| SuperTrend line | OUT_OF_SCOPE | Only current direction/value is available; no coherent historical series exists in the chart contract |
| SuperTrend direction | EXISTING | Remains textual in Technical Structure; not duplicated into chart inference |
| Live/latest quote | OUT_OF_SCOPE | Different session boundary; Stock 360 header owns it |
| Current-session candle | OUT_OF_SCOPE | Explicitly excluded after completed-D1 cutoff |
| Trend shading | METHODOLOGY_REQUIRED | No approved shading semantics |
| Buy/sell markers | METHODOLOGY_REQUIRED | No SI recommendation methodology |
| Entry markers | OUT_OF_SCOPE | Would mix Decision/TradePlan semantics into completed-D1 evidence |
| Risk/reward zones | METHODOLOGY_REQUIRED | No approved SI risk/reward methodology |
| Annotations | OUT_OF_SCOPE | No approved event/annotation series in this contract |
| Crosshair | PRESENTATION_ONLY | Lightweight pointer/focus inspection is feasible in the existing SVG |
| Tooltip | PRESENTATION_ONLY | Date/OHLCV/SMA20/SMA50 only; no signal language |
| Zoom/pan | OUT_OF_SCOPE | Substantial new chart infrastructure; fixed deterministic window is sufficient |
| Visible date range | PRESENTATION_ONLY | Existing request stays at 180 sessions; report actual valid rendered first/last dates |

## 5. SMA calculation and missing-data policy

For valid chronological closes:

- `SMA20[t] = sum(close[t-19:t]) / 20`
- `SMA50[t] = sum(close[t-49:t]) / 50`

Warm-up entries are absent, never zero. A row is chart-valid only when its
timestamp and OHLC are finite/parseable, prices are positive, high is not
below low, and volume is finite and non-negative. The typed API normally
guarantees this; the browser validation is a fail-closed defense. Invalid rows
are omitted and counted for an explicit chart note. Calculation never reaches
past the authoritative completed-D1 date.

## 6. Levels and zone semantics

All six structural fields share the same D1 structural adapter, session, and
lineage. P2C may render every non-empty zone already present in the bundle.
No new target is created.

- When `lower != upper`, render a subtle horizontal band from exact lower to
  exact upper. Both boundaries participate in the mathematically faithful
  price domain.
- When equal at display precision, render one line.
- Never use or imply a midpoint.
- Compact labels use S1/MS/RT/T1/T2/T3. A nearby key expands each abbreviation
  and reports the exact zone with the frozen P2B money formatter.
- Available-history high stays in Price Map and is not added to the chart.

## 7. Right-edge collision finding and solution

The available TI baseline screenshot visibly places S1 and MS directly over
one another at the right edge; the current renderer emits each label at its
natural `y(price) + 3` without layout.

P2C will keep each band/line at its true price coordinate, then independently
lay out label boxes:

1. calculate each label's natural Y from the already-approved Price Map
   boundary (support upper; trigger/target lower), never a midpoint;
2. sort by natural Y and stable source order;
3. enforce a fixed minimum pixel gap inside the price plot;
4. run a reverse pass to remain inside the lower bound;
5. move label boxes only;
6. draw a leader from the true natural Y to the displaced box when needed.

Tests will prove separate label positions and unchanged true price Y values.

## 8. Scale, history, and inspection decisions

- Retain the deterministic 180-session request. It supports SMA50 warm-up,
  recent structure, levels, and volume without optimizing around a visual
  pattern. Report the actual number rendered and exact first/last date.
- Include candle highs/lows, all rendered zone boundaries, both SMA series,
  and completed close in the linear price domain before applying modest
  symmetric padding. No warped or categorical price scale.
- Allocate a dedicated volume pane and reduce unused outer margins while
  retaining readable labels.
- Add a lightweight SVG inspection overlay: pointer/tap selects the nearest
  candle; keyboard focus plus Left/Right traverses candles. The compact readout
  contains Date, O/H/L/C, Volume, SMA20, and SMA50 only.
- Do not add zoom or pan.

## 9. Accessibility and responsive plan

The chart receives a descriptive accessible label including completed-D1
semantics and range. SMA20 and SMA50 differ by label, color, and line style
(solid vs dashed), so color is not the sole identifier. Level abbreviations
are expanded in the chart key. Pointer inspection has keyboard parity.

The SVG remains fluid-width via its `viewBox`; narrow CSS stacks the legend/key,
keeps the plot within `max-width: 100%`, and prevents chart text or tooltip from
creating page overflow. Labels remain in the SVG's reserved right gutter.

## 10. Performance and network verdict

No request is added. P2C continues to use the one existing 180-candle GET.
SMA, scale, zones, collision layout, and inspection are pure in-memory chart
composition. Analyze, generation/abort behavior, and DarvaX isolation remain
unchanged.

## 11. Screenshot discovery note

The handoff-referenced `docs/research/si-p2b-live-gate/` directory is absent
from this workspace, as already recorded by the handoff. The available
`si-p1-ux-baseline/04-nse-ti-technical-chart.png` was inspected and confirms
the S1/MS right-edge collision and excess vertical whitespace. Final P2C live
validation must use unmodified real database state and capture fresh desktop
and ~390px evidence.

## 12. Stop-condition assessment

None is triggered:

- both chart and Stock 360 SMA values originate from canonical persisted D1;
- frontend series calculation has unambiguous visualization ownership and a
  mandatory final-value reconciliation gate;
- exact zones have explicit structural-review provenance;
- historical SuperTrend is unavailable and therefore excluded;
- no frozen SI contract or architecture boundary needs modification.

SI-P2D and all later milestones remain out of scope.

## 13. Post-implementation visual-refinement finding

The first correct P2C rendering exposed a presentation problem rather than a
methodology problem: the chart showed too much permanent explanatory chrome,
level labeling, and inspection furniture at once. The result was accurate but
read like an engineering diagnostic. The authorized refinement therefore
freezes the hierarchy as **price > trend > structure > detail on demand**.

The safe presentation-only changes are:

- default to a six-month view, with 3M, 6M, and All controls that slice only
  the already-loaded rows after SMA20/SMA50 have been calculated over the full
  completed-D1 history;
- keep candles visually dominant, SMA paths secondary, structural bands quiet,
  and volume subordinate;
- replace the full-width close treatment with a compact right-edge completed-D1
  tag at the exact same value;
- hide the inspection crosshair/readout and exact level tags at idle, exposing
  them through pointer, focus, keyboard, tap, or a counted Levels control;
- preserve full level names, exact zone values, lineage, and keyboard access in
  the detail-on-demand state;
- place desktop inspection over unused plot space and make narrow inspection a
  stable block above the plot rather than a pointer-following tooltip.

These choices add no network request, data transformation, analytical verdict,
or contract. Window changes are render-only views of the same 180-row payload;
the authoritative cutoff, full-history rolling calculation, reconciliation,
zone coordinates, and provenance gates remain unchanged.

## 14. Final interaction-model refinement

Review of `9.246.0` found one remaining presentation defect: its optional
"show all" state still produced a collision-safe but visually dense wall of
right-edge tags. It also relied on independently overlapping SVG hit regions,
which allowed paint order to influence which nearby level received a pointer.

The final presentation model removes that state entirely:

- idle retains faint exact structural geometry but zero structural tags;
- pointer position is resolved once against every exact level geometry, using
  minimum boundary distance and stable source order only as a geometric tie
  break;
- only the resolved, focused, tapped, or list-selected level is emphasized;
- its compact marker uses the zone's visual center for label placement only,
  while exact lower/upper values remain the displayed evidence;
- `Levels · n` opens a read-only selectable list of every approved level and
  exact zone; opening it never reveals every axis marker;
- overlapping zones remain separate geometries and separate keyboard/list
  entries;
- desktop detail moves above or below price action according to the active
  level's vertical position; narrow detail occupies stable space above the SVG.

This is geometry and interaction state, not semantic ranking. No evidence,
formula, scale, level coordinate, or architecture boundary changes.
