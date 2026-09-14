# SI-P2C — Completed-D1 Chart Intelligence Implementation

Status: **COMPLETE AND FROZEN** — Owner / Chief Architect approved 2026-09-14 — asset `9.250.0`

Date: 2026-09-13

Discovery: `docs/research/SI-P2C-CHART-INTELLIGENCE-DISCOVERY.md`

Frozen predecessors: SI-P1, SI-P2A, SI-P2B

## 1. Implementation verdict

SI-P2C is implemented, live-validated, and ready for Owner / Chief Architect
source and visual review. The Stock 360 chart now visualizes completed-D1
candles, volume, SMA20, SMA50, the completed close, and all coherent approved
structural zones already present in the frozen SI bundle. It adds no
methodology, score, signal, recommendation, provider read, API request, or
backend contract.

SI-P1/P2A/P2B remain complete and frozen. SI-P2D and later milestones have not
started.

## 2. Exact chart changes

- Calculate and draw deterministic trailing SMA20 and SMA50 paths from the
  chart's already-loaded completed-D1 closes.
- Show a compact single-row legend for SMA20, SMA50, and completed-D1 close.
  SMA20 is solid amber; SMA50 is dashed violet; labels make color non-essential.
- Render coherent Support 1, Major Support, Review Trigger, and Target 1–3 as
  exact bands when lower/upper differ, or a line when equal.
- Keep structural labels hidden at idle; expose a counted Levels list and
  focusable exact-level detail with expanded name, value, and lineage. Only one
  contextual axis marker can be active at a time.
- Preserve true level coordinates while laying out right-edge labels with
  deterministic minimum spacing and leader lines for displaced labels.
- Add a short exact completed-D1 close guide and compact right-edge D1 tag.
- Add a faithful linear price grid, a larger volume pane, reduced outer
  whitespace, and actual rendered-session/date-range metadata.
- Add pointer/tap inspection and keyboard Left/Right/Home/End traversal for
  Date, OHLC, Volume, SMA20, and SMA50; keep it absent at idle and support
  Escape dismissal.
- Add 3M, 6M, and All visible-window controls over the already-loaded payload,
  defaulting to 6M. Full-history SMA calculation and final reconciliation occur
  before any visible-window slice.
- Use an actual-host-width compact chart geometry below 520px so labels and
  axes remain legible at ~390px without horizontal SI overflow.
- Bump the static asset pin from `9.244.0` through `9.250.0` in the dashboard host,
  SI stylesheet import, and frozen release-gate tests.

## 3. SMA implementation and ownership

SMA paths are calculated in `08c-symbol-intelligence.js` using pure rolling
arithmetic over the already-returned chart candle payload:

- first SMA20 after exactly 20 valid closes;
- first SMA50 after exactly 50 valid closes;
- warm-up positions remain null and are not plotted;
- no future or post-cutoff value can enter a window.

This is the correct owner for the plotted series because it is deterministic
chart composition over the exact already-loaded D1 rows. The frozen backend
`PortfolioTrendAdapter` remains authoritative for Stock 360's final SMA values
and textual Daily SMA structure. Adding a second chart-series DTO or endpoint
would needlessly expand a frozen contract.

## 4. PIT and completed-session safety

`d1.latest_session` from the frozen SI bundle is the chart's authoritative
completed-session cutoff. Chart preparation:

1. validates and sorts returned rows chronologically;
2. excludes every row whose market date is later than the cutoff (including an
   unfinished current-session row if one appears in the generic candle read);
3. excludes invalid OHLCV rows explicitly and reports a count;
4. calculates both SMA series only on the retained sequence;
5. verifies the final chart close against `d1.close` at two-decimal display
   precision before rendering.

No live/latest quote enters chart scale, levels, close, or SMA calculations.

## 5. Final-value reconciliation evidence

The chart compares each available calculated final SMA with the frozen
`d1.fast_sma` / `d1.slow_sma` at Stock 360's two-decimal display precision.
If either differs, that SMA path and legend value fail closed as
`COHERENCE UNAVAILABLE`; the chart never paints two different values. A close
mismatch fails the whole chart closed.

Real localhost validation on 2026-09-13:

| Symbol | Completed D1 | Stock 360 SMA20 / SMA50 | Chart SMA20 / SMA50 | Result |
|---|---|---|---|---|
| NSE:WIPRO | 2026-09-11 | ₹176.77 / ₹178.71 | ₹176.77 / ₹178.71 | Exact display reconciliation |
| NSE:TI | 2026-09-11 | ₹556.74 / ₹504.25 | ₹556.74 / ₹504.25 | Exact display reconciliation |

At 20–49 valid candles, chart SMA20 is deterministically available while
SMA50 is unavailable. The existing backend trend adapter withholds its final
SMA fields until the 50-candle trend contract is evaluable; the chart reports
that its comparison value is unavailable rather than claiming reconciliation.
Below 20, both paths are unavailable. No frozen adapter behavior was changed.

## 6. Level and zone behavior

Only zones with `structural_is_coherent === true` and exact
`PORTFOLIO_STRUCTURAL_REVIEW` lineage render. Non-empty S1, MS, RT, T1, T2,
and T3 therefore share the existing structural adapter's session/provenance.

- Unequal lower/upper: exact translucent band plus both exact boundary edges.
- Equal at two decimals: one exact line.
- S1/MS label anchors use the already-approved upper boundary.
- RT/T1/T2/T3 label anchors use the already-approved lower boundary.
- No midpoint is calculated or implied.

Available-history high is deliberately excluded because the Price Map already
provides it and adding another remote line materially compresses ordinary price
structure. It remains correctly named and is never called 52-week high or ATH.

## 7. Collision solution

Only one contextual structural tag can render, so production layout compares
that tag directly with the persistent D1 tag. `siChartPlaceLevelTag()` receives
the structural natural Y, immutable D1 Y, plot bounds, both exact box heights,
and a six-pixel minimum gap. D1 remains fixed. The structural box moves above
or below it using deterministic available-space and nearest-displacement rules;
its leader and anchor retain the true structural Y. Prices, scale, bands, and
the D1 tag never move.

The production renderer calls this same pure helper for every potential active
tag. Its behavioral test proves non-overlapping intervals and unchanged source
anchors. Real WIPRO validation exercises the close case naturally: Major
Support at ₹169.00 and D1 at ₹167.40 render separately with a visible leader.

## 8. Tooltip / crosshair decision

A lightweight inspection readout and vertical crosshair were implemented
inside the existing custom SVG—no chart library or new subsystem. Pointer move
updates the nearest session; tap selects; keyboard focus plus Left/Right and
Home/End provides equivalent traversal. Inspection contains only Date, OHLC,
Volume, SMA20, and SMA50.

Zoom/pan remains deferred because it would add disproportionate infrastructure
to a fixed 180-session research chart.

## 9. Responsive behavior

The final renderer uses the actual chart-host width at every breakpoint rather
than proportionally enlarging a fixed desktop viewBox. Desktop height is capped
at 460px (420px in the intermediate layout); a chart host below 520px uses a
350px height and compact faithful margins. Price and volume panes are derived
from that bounded height. The SVG remains `width: 100%`, `max-width: 100%`, and
supports vertical touch scrolling.

Live ~390px validation with the existing global rail collapsed showed candles,
both SMA styles, volume, axes, compact controls, legend, metadata, and a stable
inspection block above the plot without SI horizontal overflow. WIPRO and TI
were both checked. The global expanded-rail behavior was not redesigned, per
scope.

## 9A. Visual refinement outcome

The post-implementation pass deliberately removed the debug-panel feel without
removing evidence. Candles now carry primary contrast; SMA paths are thinner;
grid, axes, bands, volume, and crosshair recede in that order. Exact structural
tags appear only for the focused/hovered level or when the owner opens the
counted Levels control. Desktop inspection floats compactly over unused plot
space; narrow inspection reserves stable space above the plot. The chart's idle
state therefore communicates price and trend first while all exact evidence
remains reachable.

## 9B. Final structural interaction and polish outcome

Asset `9.247.0` removed the remaining all-tags mode. `Levels · n` opened a
compact read-only list containing every approved level and exact zone. Hover,
focus, tap, or list selection emphasizes exactly one underlying geometry and
reveals exactly one contextual marker. Other structural geometry remains faint
and visible. Closing the list, pointer exit, outside chart interaction, or
Escape restores the calm state according to input mode.

Pointer selection no longer depends on overlapping SVG hit targets. One
resolver compares the pointer's vertical coordinate to every exact line/band,
selects the nearest boundary, and uses stable source order only for an exact
geometric tie. TI's exactly overlapping Review Trigger and Target 1 therefore
remain distinct evidence while a single pointer position activates only one.
No semantic priority is implied.

The header now pairs title/subtitle with a separated window group and Levels
control, followed by one lighter legend row. The left plot margin is tighter,
the grid lighter, and the plotting surface uses an inset edge instead of a
second strong border. Completed D1 remains the only persistent right-axis tag.
The candle inspector is narrower, two-line, date-led, and moves horizontally
away from the selected candle. Active level detail moves vertically away from
high/low structures. At 390px structural axis tags are suppressed entirely;
the exact selected-level card and full-width compact Levels list provide the
touch/keyboard interaction.

## 9C. Screenshot-driven world-class closure

Asset `9.248.0` corrects the final composition defects found in the Owner's
full-width screenshots without changing any financial or interaction
semantics:

- desktop geometry now uses the host's actual logical width with a capped
  460px plot height instead of proportionally enlarging the 840×430 canvas;
- a guarded `ResizeObserver` recomposes the chart after real host-width changes
  while preserving the selected 3M/6M/All window;
- price ticks use a deterministic 1/2/2.5/5/10 nice-step scale that expands,
  never clips, the true candle/SMA/structural domain;
- time ticks adapt to two narrow, three standard, or five wide anchors and sit
  directly below a denser, separated volume pane;
- the completed-D1 marker is a quiet dark right-axis tag rather than a bright
  button-like capsule;
- inactive structural zone edges recede; menu inspection highlights only the
  chosen geometry, while direct chart inspection exposes one compact gutter
  tag and no detached desktop detail card;
- candle inspection stays near the selected session, the crosshair recedes,
  and the selected candle receives a local outline;
- controls, legend, menu width, title rhythm, and nested framing were tightened.

Final real-browser evidence is retained under
`docs/research/si-p2c-world-class-chart-closure/`.

## 9D. Final level and range-state correction

Asset `9.249.0` resolves the Owner's final screenshot observations without
changing chart data, scale, coordinates, or request behavior:

- desktop contextual level tags increase to 150×24 SVG pixels with 11px
  semibold type and clearer abbreviation/value separation;
- active zones retain their exact filled band and boundary strokes, while a
  presentation-only minimum-10px halo makes narrow ranges visibly selectable;
- touch, keyboard, and menu selections received stronger visual emphasis, but
  the subsequent source review found their state ownership was still coupled
  to transient pointer/focus inspection and required the `9.250.0` correction;
- 3M/6M/All selected, hover, and keyboard-focus styles are visually distinct;
  the selected state remains driven by the existing `aria-pressed` truth;
- the desktop right gutter expands only enough to contain the larger tag; and
- live browser assertions prove exactly one selected window with 63/126/180
  completed sessions, one active level annotation, preserved responsive
  geometry, and zero page errors or overflow.

Historical SuperTrend remains outside SI-P2C because the current frozen
contract exposes only its latest value/direction, not a coherent PIT-safe
series. No frontend approximation or misleading horizontal line was added.

## 9E. Final interaction / collision / mobile closure

Asset `9.250.0` closes the final source-review blockers:

- `siChartCreateLevelInteraction()` owns persistent selection separately from
  transient hover/focus preview. Active identity resolves as transient first,
  then persistent, then none. Preview exit restores the selected level;
- mouse click, touch, keyboard activation, and menu selection persist exactly
  one level. Escape clears preview/selection; blank-chart click clears the
  structural selection; closing or clicking outside the menu preserves it;
- menu `active` state follows the displayed identity while `is-selected` and
  `aria-selected` follow only persistent identity, preventing chart/list drift;
- the production renderer invokes `siChartPlaceLevelTag()` for each contextual
  tag, reserving the immutable D1 interval and moving only the structural box;
- desktop active-level inspection exposes full name, exact value/zone,
  Portfolio Structural Review provenance, and completed-D1 context;
- narrow Levels disclosure is an in-flow local-card-width list. Selecting a row
  collapses it, preserves geometry, and reveals a stable in-flow inspector;
- compact margins change from 34/36 to 32/12 at the measured 220px SVG. Plot
  width increases from 138 to 176 units (27.5%; 66% to 80% utilization) without
  changing the global rail;
- desktop reserve tightens from 166px to 112px. The contextual axis tag becomes
  a concise 52×24 abbreviation anchored to the full inspector, avoiding idle
  dead space without activation-time reflow;
- price scale keeps exact six-percent domain padding and chooses deterministically
  among multiple nice intervals for a bounded 2–7-tick density; tick rounding
  no longer expands the plotted domain beyond that padding;
- the active halo tightens from a minimum 10px/eight-pixel stroke to a minimum
  6px/four-pixel stroke, with exact bands carrying the stronger emphasis; and
- candle inspection now groups OHLC into aligned pairs, separates volume, and
  gives SMA20/SMA50 a subordinate structured row on desktop and in-flow mobile.

Final evidence is retained under
`docs/research/si-p2c-final-interaction-closure/`.

## 10. Performance and network impact

Zero new requests. P2C retains exactly one existing
`candles?timeframe=1d&limit=180` GET after SI composition. SMA, zone drawing,
label layout, crosshair selection, and scaling are local pure operations over
at most 180 rows. Analyze and its generation/AbortController lifecycle are
unchanged.

## 11. Tests and static checks

New behavioral/static coverage:

- SMA20 unavailable at 19, available/correct at 20, rolling arithmetic;
- SMA50 unavailable at 49, available/correct at 50;
- future/current-session row and invalid-row exclusion;
- final close/SMA coherence and fail-closed mismatch;
- approved zone provenance and all S1/MS/RT/T1/T2/T3 mappings;
- no midpoint behavior;
- production-wired D1/structural-tag separation without anchor mutation;
- persistent T1 selection → transient T2 preview → T1 restoration, plus
  mouse-click persistence and full clear behavior through the production state
  owner;
- legend, close marker, idle-hidden inspection, Escape dismissal, keyboard
  support, level disclosure, and responsive geometry;
- 3M/6M/All slicing after full-history SMA calculation;
- one-request lifecycle, invalid-symbol no-host behavior, and `9.250.0` pins;
- clean price-scale ticks, adaptive date density, bounded wide geometry, and
  resize recomposition.

Results:

- focused P2C: **19 passed** after final interaction/collision/mobile closure;
- final integrated SI/API/hosting/chart regression: **55 passed**;
- full suite: **4078 passed, 0 failed, 2 skipped**;
- Ruff (new P2C test): **passed**;
- mypy (`src/athena/symbol_intelligence`): **passed, 4 source files**;
- JavaScript syntax (`node --check`): **passed**;
- `git diff --check`: **passed** before documentation closeout.

## 12. Live validation and screenshot evidence

Already observed against the real running localhost service and unmodified
`db/athena.db`:

- WIPRO: downtrend, exact SMA reconciliation, T1/T2/T3 present;
- TI: SMA/SuperTrend disagreement, uptrend SMA structure, close S1/MS and
  RT/T1 label pairs, desktop and ~390px compact chart;
- keyboard inspection: moved from 2026-09-11 to 2026-09-10 with the matching
  OHLCV/SMA readout.

Captured in the live browser against unmodified persisted data:

1. WIPRO desktop idle at the default 6M window;
2. WIPRO desktop candle inspection with exact OHLCV/SMA values;
3. WIPRO focused Major Support with exact value and provenance;
4. WIPRO 3M showing 63 of 180 sessions while final SMA values remain equal;
5. TI desktop with all four labels exposed, proving RT/T1 and S1/MS collision
   handling while preserving the uptrend SMA structure;
6. WIPRO ~390px idle and inspected states;
7. TI ~390px inspected state.

The natural WIPRO payload also supplies T1/T2/T3 coverage. No database state
was manufactured. The live renderer booted without a chart library and used
the existing single candle request.

The nine PNGs and their evidence mapping are retained in
`docs/research/si-p2c-chart-ux-refinement/README.md`.

The final interaction/polish capture set is retained in
`docs/research/si-p2c-level-interaction-polish/README.md`.

The final 12-state desktop/mobile interaction, collision, and width-recovery
set is retained in
`docs/research/si-p2c-final-interaction-closure/README.md`.

## 13. Owner-review answers

1. **Where are SMA20/SMA50 calculated?** The plotted series are calculated in
   the SI frontend from the one completed-D1 payload; authoritative final
   values/text remain in the frozen backend trend adapter.
2. **Why there?** Plotting every historical point is deterministic presentation
   over data already in the browser and needs no DTO/API expansion.
3. **PIT safety?** Authoritative `d1.latest_session` cutoff, chronological valid
   rows only, later/current rows excluded before rolling windows.
4. **Reconciliation?** WIPRO and TI match exactly at display precision; a
   mismatch hides the affected overlay and says why.
5. **Zones?** Exact lower-to-upper bands; equal zones become one line; no
   midpoint.
6. **Collisions?** The one active structural tag is deterministically laid out
   against the fixed D1 tag with a minimum gap and leader; true price Y and
   zone boundaries never move.
7. **Which levels?** Coherent, correctly-provenanced S1/MS/RT/T1/T2/T3 when
   present.
8. **Excluded levels?** Available-history high to prevent scale compression and
   clutter; incoherent/wrong-lineage/empty zones fail closed.
9. **Historical SuperTrend?** Not safely available; only the current textual
   value/direction exists, so no line is fabricated.
10. **Network calls?** None added; still one existing 180-candle GET.
11. **Below 20/50?** `<20`: no SMA20; `<50`: no SMA50; available candles still
   render. SMA20 begins exactly at 20.
12. **Later chart work?** Optional zoom/pan, historical SuperTrend only after an
   approved coherent series exists, live-quote/current-session overlays only
   after explicit session semantics, and any richer annotations in separately
   authorized future milestones.

## 14. Files

Created:

- `docs/research/SI-P2C-CHART-INTELLIGENCE-DISCOVERY.md`
- `docs/research/SI-P2C-CHART-INTELLIGENCE-IMPLEMENTATION.md`
- `docs/research/si-p2c-final-interaction-closure/` evidence
- `tests/symbol_intelligence/test_si_p2c_chart_intelligence.py`

Modified:

- `src/athena/api/static/js/08c-symbol-intelligence.js`
- `src/athena/api/static/css/15-symbol-intelligence.css`
- `src/athena/api/static/dashboard.css`
- `src/athena/api/static/index.html`
- SI-P2A/P2B and dashboard/chart asset-pin regression tests
- `docs/MILESTONES.md`
- `ATHENA_BRIEFING.md`
- `IMPLEMENTATION_SUMMARY.md`

Public API/DTO/schema changes: **none**.

## 15. Known limitations and explicit deferrals

- Final SMA comparison is at the frozen two-decimal presentation precision.
- At 20–49 rows, frontend SMA20 is valid but the frozen trend adapter has no
  comparison value until its 50-candle contract is evaluable; this is disclosed.
- The generic candle endpoint itself remains generic; the SI renderer owns its
  completed-session filter using the bundle cutoff.
- No historical SuperTrend, live quote, current-session candle,
  available-history-high line, zoom/pan, event annotation, trade marker,
  risk/reward zone, or predicted level.
- SI-P2D written-summary work, SI-P2E Decision behavior, and SI-F0/SI-N0 data
  tracks remain not started and not authorized.

## 16. Refinement verification closeout

- P2C behavioral/static tests: **19 passed** after final interaction/collision/mobile closure.
- Final integrated SI/API/hosting/chart regression: **55 passed**.
- Full suite: **4078 passed, 0 failed, 2 skipped**.
- Ruff: passed.
- Scoped mypy: passed, 4 source files.
- JavaScript syntax: passed.
- `git diff --check`: passed before final documentation closeout and rerun at
  handoff.

Following Owner / Chief Architect final source, interaction, collision, mobile,
and evidence approval, SI-P2C is COMPLETE AND FROZEN on asset `9.250.0`.

## 17. Consolidated commit message

```text
feat(review): complete SI-P2C chart intelligence

- Plot PIT-safe completed-D1 candles, volume, and reconciled SMA20/SMA50 series.
- Add exact structural zones, accessible level selection, and responsive inspection.
- Resolve D1 tag collisions and persistent/transient interaction state.
- Preserve one request and all frozen SI, Portfolio, and Decision contracts.
- Record approved desktop/mobile evidence and freeze asset 9.250.0.
```

**Milestone stop:** SI-P2C — COMPLETE AND FROZEN following Owner / Chief
Architect source, interaction, collision, mobile, and final evidence approval on
2026-09-14. Do not start SI-P2D without separate authorization.
