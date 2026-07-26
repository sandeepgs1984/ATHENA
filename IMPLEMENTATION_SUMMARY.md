# ATHENA — Implementation Summary

Permanent implementation log. One section per completed phase, newest first,
in the 7-part format mandated by CLAUDE.md. Written before owner review;
status updated on approval.

---

## UX-3b — Chart ATR/moving-average/volume overlay (READY FOR REVIEW)

| | |
|---|---|
| Completed | 2026-07-26 |
| Objective | "Professional mini-TradingView style" chart (owner UX audit #11): the intraday chart gains a moving-average line, an ATR volatility envelope, and a volume subplot |
| Scope | New `atr_series`/`sma_series` pure functions in `indicators/calculations.py` (existing scalar `atr()`/`sma()` now delegate to them — byte-identical output); `CandleDTO` gains optional `atr`/`moving_average` fields, populated by `MarketHistoryService.recent_candles` using the same config-driven periods (`config/indicators.json`) already used elsewhere; frontend chart renders the MA line, ATR band, and volume bars; also fixed Entry Zone showing "₹X – ₹X" when low==high |
| Tests | Full suite **1017 passed** (+1 backend test verifying the service's per-candle output matches the pure functions exactly); Ruff clean; mypy currently unavailable in this environment (missing since earlier in the session, unrelated to this change) — types manually reviewed |
| Coverage | Existing project coverage retained |
| Status | **READY FOR REVIEW** |
| Branch | feature/live-dashboard |

### Scope completed

- **`atr_series`/`sma_series`** (`indicators/calculations.py`): full per-bar
  series versions of the existing scalar `atr()`/`sma()`, retaining every
  intermediate Wilder-smoothed/rolling-window value instead of discarding
  all but the last. The scalar functions now **delegate** to the series
  functions (`series[-1]`) rather than duplicating the math — guarantees
  the chart's ATR/MA line and the TradePlan's D1-based sizing can never
  silently diverge from the same underlying computation. Verified
  byte-identical against the pre-existing `tests/decision/test_indicators.py`
  suite (26 tests, all still pass unchanged).
- **`align_trailing_series`**: pads a trailing series (which starts partway
  through the candle history, once enough bars exist) with `None` for the
  warmup prefix — honest "not yet computable," never an invented early
  value.
- **`CandleDTO.atr`/`.moving_average`** (both `Decimal | None`, default
  `None`): additive fields, no existing consumer breaks.
  `MarketHistoryService.recent_candles` computes both using the exact same
  periods already configured in `config/indicators.json` (`atr.period=14`,
  `sma.period=20`) — no new config, no duplicated thresholds.
- **Chart rendering** (`renderCandlestickSvg`): a moving-average polyline,
  a semi-transparent ATR envelope (MA ± ATR, filled only across indices
  where both values are actually known — never interpolated across a
  gap), and a volume bar subplot beneath the price chart (up/down colored
  to match the candle bodies above it). Y-axis scaling now also accounts
  for the ATR band's price range so it's never clipped. Legend gained
  "Moving average," "ATR band," and "Volume" entries.
- **Entry Zone display fix** (owner-reported): when `entry_low ==
  entry_high`, the Trade Plan card now shows the single price instead of
  "₹13,781.00 – ₹13,781.00," which read as a rendering glitch.

### Files created

- None.

### Files modified

- `src/athena/indicators/calculations.py` — `sma_series`, `atr_series`,
  `align_trailing_series`; `sma`/`atr` now delegate to their series.
- `src/athena/api/v1/dtos/market.py` — `CandleDTO.atr`/`.moving_average`.
- `src/athena/api/v1/services/market_history_service.py` — `config_dir`
  constructor param; computes/attaches the aligned series per candle.
- `src/athena/api/dependencies.py` — `get_market_history_service` passes
  `config_dir`.
- `tests/api/v1/test_market_history.py` — new test verifying per-candle
  output matches `atr_series`/`sma_series` exactly, warmup is honestly
  `None`.
- `src/athena/api/static/dashboard.js` — `renderCandlestickSvg` gains the
  MA/ATR/volume rendering; chart legend entries; `renderTradePlan`'s
  entry-zone single-value fix.
- `src/athena/api/static/dashboard.css` — `.decision-chart-ma-line`,
  `.decision-chart-atr-band`, `.decision-chart-volume-bar` (+ legend
  swatches).
- `tests/api/platform/test_dashboard_hosting.py` — new assertions.
- `docs/MILESTONES.md` — UX-3a flipped to Approved, UX-3b → Ready for review.
- Cache-bust: `9.34.0` → `9.35.0`.
- This log.

### Public APIs

- `CandleDTO` gains two additive, optional fields (`atr`, `moving_average`)
  — backward compatible, no existing consumer breaks. No other API surface
  changed.

### Validation and architecture

- Full regression: **1017 passed** (was 1016; +1 new backend test).
- Ruff clean on every touched file. mypy unavailable in this environment
  (disappeared from the toolchain since earlier in this session, unrelated
  to this change) — reviewed all touched signatures/types manually;
  existing `tests/decision/test_indicators.py` (26 tests) confirms the
  scalar/series delegation produces identical output.
- JS brace/paren balance checked against the pre-edit baseline; live
  server restart (clean startup — confirms the new config-loading path
  works) + isolated-browser console check: zero errors on load.
- No order-placement path touched. ADR-005 preserved: ATR/MA are pure,
  deterministic, already-existing-formula computations over persisted
  candle history — never generated, never a second independently-derived
  number (the scalar TradePlan-sizing ATR and the chart's ATR line share
  one function). No ADR required — additive DTO fields, not a domain
  object change.

### Risks and technical debt

- I could not exercise the redesigned chart end-to-end myself (no owner
  credentials) — needs an owner click-through, especially to confirm the
  ATR band/MA line/volume subplot read clearly rather than adding clutter.
- mypy being unavailable in this environment is a pre-existing
  environment issue, not something this change introduced or can fix —
  flagging for awareness, not treating as this milestone's technical debt.
- No new technical debt beyond the above.

### Remaining work

- **Owner smoke test**: open a decision with enough candle history (≥21
  bars) to clear both the ATR (14) and SMA (20) warmup periods; confirm
  the moving-average line and ATR band render sensibly against price;
  confirm the volume subplot reads clearly; confirm a short-history
  decision (< 21 bars) shows the chart with no MA/ATR line rather than an
  error. Confirm the Entry Zone single-value fix reads correctly for a
  zero-width entry.
- This closes out **UX-3** (both 3a and 3b). Next in the UX Overhaul
  program: **UX-4** (tab renaming + progressive disclosure + Market
  Context cards).

### Commit message

```text
feat(indicators,dashboard): add ATR/moving-average/volume chart overlay (UX-3b)

- Add atr_series/sma_series pure functions to indicators/calculations.py; existing scalar atr()/sma() now delegate to them (byte-identical output, verified by the existing 26-test indicator suite) so the chart and TradePlan sizing can never silently diverge
- Add CandleDTO.atr/.moving_average (additive, optional) and align_trailing_series for honest None-padding during warmup, never an invented early value
- Wire MarketHistoryService.recent_candles to compute both using the same config/indicators.json periods already used elsewhere (atr=14, sma=20), no new config
- Add moving-average line, ATR envelope, and volume subplot to renderCandlestickSvg; fix Entry Zone showing "X - X" when entry_low equals entry_high
```

---

## UX-3a — Trade Plan visual redesign (APPROVED)

| | |
|---|---|
| Completed | 2026-07-26 |
| Objective | Third milestone of the owner's UX audit: "huge numbers, professional" — the Trade Plan's entry/stop/target/R:R deserve the same visual weight as the cockpit gauges, not small dense text |
| Scope | `renderTradePlan` restructured into a hero-metric grid; new **Expected Return %** figure computed from the plan's own persisted `entry_low`/`entry_high`/`targets[0]` (pure arithmetic, never invented) |
| Tests | Full suite **1016 passed**; new assertions; no backend files touched |
| Coverage | Frontend-only change; no Python coverage impact |
| Status | **APPROVED** (owner smoke confirmed live 2026-07-26 — math verified against the live screenshot) |
| Branch | feature/live-dashboard |

### Scope completed

- **Trade Plan hero grid**: Entry zone, Stop, Target(s), Expected Return,
  Risk:Reward each get their own bordered metric card with a large
  (1.15rem mono) value — the same visual language as the cockpit gauges —
  replacing the old dense 2-column grid of small text. Model units/risk
  amount moved to a smaller secondary row underneath (still shown, just
  de-emphasized relative to the tradeable levels).
- **Expected Return %** (`computeExpectedReturnPct`): `((target - entryMid)
  / entryMid) * 100`, using the nearest target (`targets[0]`) since that's
  the one most likely to be hit; sign-flipped for SHORT decisions. When a
  plan has more than one target, the caption reads "to T1" so it's never
  ambiguous which target the percentage refers to. Pure arithmetic over
  already-persisted `TradePlan` fields — no new backend field, nothing
  invented, per ADR-005.
- Removed the now-dead `.trade-plan-grid`/`.trade-plan-metric` CSS (only
  consumer was the old template, and the DAG-panel duplicate that rendered
  it was already removed in an earlier milestone).

### Files created

- None.

### Files modified

- `src/athena/api/static/dashboard.js` — `computeExpectedReturnPct`;
  `renderTradePlan` signature gains `direction`; call site updated.
- `src/athena/api/static/dashboard.css` — `.trade-plan-hero-grid` (+
  `-metric`/`-label`/`-value`/`-caption`), `.trade-plan-secondary-row`;
  removed dead `.trade-plan-grid`/`.trade-plan-metric` rules.
- `tests/api/platform/test_dashboard_hosting.py` — new assertions.
- `docs/MILESTONES.md` — UX-3 split into UX-3a (this) and UX-3b (chart
  ATR/MA/volume overlay, researched but not yet implemented).
- Cache-bust: `9.33.2` → `9.34.0`.
- This log.

### Public APIs

- None — pure frontend change.

### Validation and architecture

- Full regression: **1016 passed**. No Ruff/mypy scope.
- JS brace/paren balance checked against baseline; live server restart +
  isolated-browser console check: zero errors on load.
- ADR-005 preserved: Expected Return % is arithmetic over already-persisted
  fields, never generated or invented. No ADR required.

### Risks and technical debt

- None beyond needing an owner click-through (no login credentials).

### Remaining work

- **Owner smoke test**: open a TRADE decision, confirm Entry/Stop/Target/
  Expected Return/R:R all read clearly at the new size; confirm Expected
  Return's sign and "to T1" caption make sense for both LONG and SHORT
  decisions if you have one of each.
- **UX-3b** (chart ATR/moving-average/volume overlay) is scoped but not yet
  implemented — see `docs/MILESTONES.md` for the research summary. Owner
  go-ahead already given; will implement as its own change set given the
  backend work involved (new indicator series functions + DTO extension).

### Commit message

```text
feat(dashboard): redesign Trade Plan with hero-sized numbers and Expected Return % (UX-3a)

- Restructure renderTradePlan into a hero-metric grid (Entry/Stop/Target/Expected Return/R:R), matching the cockpit gauges' visual weight instead of small dense text
- Add computeExpectedReturnPct: pure arithmetic over the plan's own persisted entry/target values, sign-aware for SHORT decisions, captioned "to T1" when there's more than one target
- Remove dead .trade-plan-grid/.trade-plan-metric CSS (no longer referenced after the Decisions & Trace redesign removed the DAG-panel duplicate)
```

---

## UX-2 — Score/Confidence/Risk storytelling (READY FOR REVIEW)

| | |
|---|---|
| Completed | 2026-07-26 |
| Objective | Second milestone of the owner's UX audit: replace the raw dimension bars in the Analysis tab with storytelling that matches each tone — star-rated contributors for Score, a trust checklist for Confidence, a categorized hazard summary for Risk — plus a reassuring safety-gate headline and a Decision Quality Meter ladder |
| Scope | `renderAnalysisSummaryCard`/`renderAnalysisBlock` restructured to dispatch by tone; every band/percentage/star sourced from already-persisted `AnalysisDimensionDTO` fields (`value`, `level`, `weight`, `weighted`) — no client-side re-derivation of config thresholds |
| Tests | Full suite **1016 passed**; new assertions for every new function/class; no backend files touched |
| Coverage | Frontend-only change; no Python coverage impact |
| Status | **READY FOR REVIEW** |
| Branch | feature/live-dashboard |

### Scope completed

- **Score contributors as storytelling** (`renderScoreContributors`, `starRating`,
  `starGlyphs`, `dimensionContributionPct`): dimensions ranked by actual
  value (highest first), each shown as a 1-5 star rating plus its *real*
  contribution percentage — computed from the already-persisted `weight`/
  `weighted` fields on `AnalysisDimensionDTO` (`weighted / sum(weighted)`),
  never a client-side copy of `config/scoring.json`'s weight table that
  could silently drift out of sync with the real config.
- **Confidence as "why ATHENA trusts this"** (`renderConfidenceChecklist`,
  `CONFIDENCE_TRUST_LABELS`): the six raw dimension names (evidence
  completeness, data freshness, indicator availability, cross-engine
  agreement, unknown ratio, consistency) become a ✔/✘ checklist with plain
  labels ("Evidence is complete," "Engines agree with each other"). Trust
  vs. flag comes entirely from the backend's own persisted `level`
  (anything not `LOW` counts as trusted) — no new numeric threshold
  invented client-side.
- **Risk as a categorized "Major Risks" summary** (`renderRiskSummary`):
  the six raw dimensions (volatility/liquidity/gap/event/market-environment/
  concentration risk) sorted by severity (highest first), each banded
  Low/Medium/High via the same `riskBand` helper the Hero cockpit gauge
  already uses — one hazard scale throughout, never two disagreeing ones.
- **Decision Quality Meter** (`qualityLadder`, `QUALITY_LADDER_BANDS`): a
  5-segment ladder (Weak→Excellent) under the Score summary card, marking
  the same band word already shown above it — Score has no backend-computed
  level (`scoring.json` carries no levels block), so `analysisPresentation`
  now derives a `displayBand` per tone: Score uses the client `qualityBand`
  (same one from UX-1's Hero gauge); Confidence/Risk keep showing their
  real backend level, never overridden by a client approximation.
- **Safety checklist summary** ("All safety checks passed" / "Blocked on N
  of M safety checks") — a reassuring headline over the exact same gate
  results already listed below it, not a separate computation.
- **Fix pass, same turn** (owner live screenshots, cache-bust `9.32.1`):
  found two bugs while reviewing the screenshots closely before starting
  UX-2 — (1) the Hero cockpit gauges banded a fabricated "Weak"/"0.0" for a
  block whose depth status wasn't `"OK"` (Decision Banner correctly said
  "score 66.92," gauge said "Weak 0.0" for the same decision) — fixed by
  gating the band/value/bar entirely on `status === "OK"`, showing
  "Unknown"/"—" otherwise, matching what the Executive Summary already did
  correctly; (2) the Reasoning Trace's automatic "highlight stage 0 on
  load" was calling the same tab-jump logic as a real click, silently
  overriding whichever tab the trader had chosen every time they picked a
  new decision — fixed via `selectNode(stageId, { userInitiated })`, which
  only jumps tabs when `userInitiated` is true.

### Files created

- None (all additive/restructuring within existing files).

### Files modified

- `src/athena/api/static/dashboard.js` — `dimensionContributionPct`,
  `dimensionExplanationBody`, `starRating`, `starGlyphs`,
  `renderScoreContributors`, `CONFIDENCE_TRUST_LABELS`,
  `renderConfidenceChecklist`, `renderRiskSummary`, `qualityLadder`,
  `QUALITY_LADDER_BANDS`; `analysisPresentation` extended with
  `displayBand`; `renderAnalysisSummaryCard`/`renderAnalysisBlock`
  restructured; safety-checklist summary line in `renderDecisionBrief`;
  `renderCockpitGauges` status-gating fix; `selectNode` `userInitiated` fix.
- `src/athena/api/static/dashboard.css` — `.analysis-summary-band`,
  `.quality-ladder`, `.score-contributor-row`, `.trust-checklist-row`,
  `.risk-summary-row`, `.risk-band-chip`, `.safety-checklist-summary`.
- `tests/api/platform/test_dashboard_hosting.py` — new assertions.
- `docs/MILESTONES.md` — UX-1 flipped to Approved, UX-2 → Ready for review.
- Cache-bust: `9.32.0` → `9.32.1` (fix pass) → `9.33.0` (UX-2) → `9.33.1`
  (second fix pass, below).
- This log.

### Second fix pass (2026-07-26, owner live screenshots of UX-2)

Owner-reviewed the live Score/Confidence/Risk breakdowns closely; one real
issue found and fixed:

- **Score contributors were sorted by star rating, not by actual
  contribution.** A dimension with 4 stars but only 12% of the score
  (Liquidity) was listed above one with 3 stars but 21% (Market Quality) —
  since the whole point of the list is "what actually drove the score,"
  ranking by raw value instead of the real weight-derived contribution
  produced a confusing order. Fixed: `renderScoreContributors` now sorts by
  `contributionPct` (falling back to raw value only when a dimension has no
  persisted `weighted` figure to rank by).
- Also bumped the Decision Quality Meter ladder's visual weight slightly
  (4px → 6px, added a subtle highlight ring on the active segment) since it
  was hard to confirm from a screenshot whether it was rendering at all.

### Third fix pass (2026-07-26) — Decision Timeline moved out of the Context tab

Owner-reported: the Decision Timeline's entries aren't just a history
display — clicking one actually switches the entire brief to that other
decision (`renderDecisionTimeline`'s rows already called `selectBriefing`),
but it was buried inside the Context tab where that significance wasn't
obvious. Moved it into `.decision-brief-hero` — the section that already
renders once per decision, outside all four tab panes, right below the
Decision Banner/Executive Summary — so it's now visible regardless of which
tab is active, with an explicit hint ("Click an entry to view ATHENA's
assessment at that point in time") for discoverability. No function
changed, no new element ids — same `renderDecisionTimeline`/
`#decision-history-timeline`, only relocated in the template. Cache-bust
`9.33.2`. Full suite still **1016 passed**; live server restart + browser
console check: zero errors.

### Public APIs

- None — pure frontend restructuring, no backend/API surface touched.

### Validation and architecture

- Full regression: **1016 passed** (unchanged — no backend files touched).
- No Ruff/mypy scope (no `.py` files changed).
- JS brace/paren balance checked against the pre-edit baseline after every
  edit in this turn; live server restart + isolated-browser console-error
  check after both the fix pass and UX-2: zero errors on load.
- ADR-005 preserved: every star/percentage/checklist tick is arithmetic or
  a direct read of an already-persisted field (`value`, `level`, `weight`,
  `weighted`), never generated or client-invented. No ADR required.

### Risks and technical debt

- I could not exercise the redesigned Analysis tab end-to-end myself (no
  owner credentials) — needs an owner click-through.
- No new technical debt beyond the above.

### Remaining work

- **Owner smoke test**: expand Score/Confidence/Risk breakdowns on a few
  decisions; confirm star ratings and contribution % look sensible against
  the raw values; confirm the confidence checklist's ✔/✘ matches what you'd
  expect from each dimension's level; confirm risk dimensions are sorted
  worst-first with sensible Low/Medium/High bands; confirm the safety
  checklist headline matches the gate list below it.
- Next in the UX Overhaul program: **UX-3** (Trade Plan visual redesign +
  chart ATR/MA overlay — needs your go-ahead on the chart backend addition
  first).

### Commit message

```text
feat(dashboard): add score/confidence/risk storytelling (UX-2); fix gauge and DAG-tab bugs

- Add renderScoreContributors: star-rated score dimensions ranked by value, with real contribution % from persisted weight/weighted fields, never a re-derived config-weight table
- Add renderConfidenceChecklist: "why ATHENA trusts this" checklist driven entirely by each dimension's real backend level
- Add renderRiskSummary: Major Risks categorized Low/Medium/High, worst first, same riskBand scale as the Hero gauge
- Add a Decision Quality Meter ladder for Score (no backend level exists for it) and a safety-checklist reassurance headline over the existing gate list
- Fix: cockpit gauges no longer band a fabricated "Weak"/"0.0" when the underlying block's status isn't OK
- Fix: Reasoning Trace's automatic first-node highlight no longer force-switches the brief's active tab — only a real click does
```

---

## UX-1 — Hero Decision Card + Executive Summary + Decision Banner (APPROVED)

| | |
|---|---|
| Completed | 2026-07-26 |
| Objective | First milestone of the owner's 40-point "ATHENA UX Overhaul" audit (`docs/MILESTONES.md`): make the top of the Decision Brief answer "what happened / why / what should I do" in under 5 seconds — meaning over decimals, an executive-briefing feel over a metrics strip |
| Scope | Sticky cockpit gauges gain band words (Strong/Good/Weak, Low/Medium/High) alongside the raw numbers; a 4th "Expected R:R" card; the old plain thesis paragraph becomes a colored Decision Banner ("ATHENA Recommendation: BUY") plus a 5-line Executive Summary composed from already-persisted engine explanations |
| Tests | Full suite **1016 passed** (new assertions for every new element); no backend files touched |
| Coverage | Frontend-only change; no Python coverage impact |
| Status | **APPROVED** (owner smoke confirmed live 2026-07-26; two bugs found and fixed in the same turn — see UX-2's fix-pass note above) |
| Branch | feature/live-dashboard |

### Scope completed

- **Band words, not just decimals** (`qualityBand`, `riskBand`): Composite
  score and Confidence get a 5-band quality word (Weak → Excellent, 40/55/
  70/85 breakpoints); Risk gets its own 3-band hazard word (Low/Medium/
  High, since "Weak risk" reads as nonsense) — both purely cosmetic
  client-side bands over the same already-computed 0-100 value, colored via
  the existing `gaugeToneColor`. The raw number moves to a smaller
  secondary caption underneath.
- **Expected R:R joins the cockpit** as a 4th gauge card, read straight from
  `decision.trade_plan.risk_reward` (no computation, `—` when there's no
  trade plan) — synchronous, no async load needed.
- **Decision Banner** replaces the plain thesis paragraph: a colored strip
  (reusing the *exact* `stance-buy`/`stance-sell`/`stance-hold`/`stance-pass`
  /`stance-wait` palette already used for the header chip — one color
  meaning throughout, never remapped) headed "ATHENA Recommendation" with
  the stance and the same reused `formatDecisionSummary().headline`
  sentence as the reason.
- **Executive Summary** (`buildExecutiveSummaryLines`, `renderExecutiveSummary`):
  up to 5 lines — gates pass/fail count, then the score/confidence/risk
  engines' own persisted `.explanation` strings verbatim (sanitized for
  numeric formatting), then a decision-type suitability line. Every line is
  either a deterministic count or a string an engine already wrote — never
  generated, per ADR-005. Gates + suitability render immediately (synchronous
  data); the three explanation lines fill in once `loadDecisionDepth`
  resolves (progressive fill, same pattern as the rest of the brief).
- **Two fields from the owner's example deliberately omitted**: "Holding:
  2-5 Days" and "Strategy: Momentum Breakout." Researched first (2026-07-26)
  — confirmed neither exists prospectively anywhere in the domain model,
  config, or DTOs (`TradeOutcome.holding_seconds` is retrospective-only,
  computed after a trade closes; the Strategy Framework can classify
  *already-completed* decisions against a strategy but never writes that
  classification back onto the `Decision`). Showing either would mean
  inventing a value — flagged instead as a possible small backend addition
  for a future milestone, not fabricated client-side.

### Fix pass (2026-07-26, owner live screenshots)

Owner approved the milestone live, but two real bugs surfaced from close-reading
the screenshots, both fixed (cache-bust `9.32.1`):

- **Gauges fabricated a "Weak"/"0.0" band for an unavailable block.** A HOLD/
  WATCH decision's Decision Banner correctly said "score 66.92/100" while
  the gauge above it showed Composite Score "Weak 0.0/100" — the Executive
  Summary correctly detected the depth report's status wasn't `"OK"` and
  omitted its lines, but `renderCockpitGauges` banded the raw value without
  checking status first. Fixed: gauges now show "Unknown"/"—" whenever the
  underlying block's status isn't `"OK"`, matching what the Executive
  Summary already did correctly.
- **Reasoning Trace's auto-highlighted first node silently overrode the
  user's chosen tab.** `selectNode()` was called both by an actual click
  and by the automatic "highlight stage 0 on load" — both paths triggered
  the same tab-jump, so picking a new decision would silently yank the
  brief back to whichever tab the first stage mapped to (usually Context),
  contradicting the stated "tab persists across decision switches" design.
  Fixed: `selectNode(stageId, { userInitiated })` only jumps tabs when
  `userInitiated` is true — the automatic initial highlight passes `false`.

### Files created

- None (all additive/restructuring within existing files).

### Files modified

- `src/athena/api/static/index.html` — gauges row expanded to 4 cards with
  band-word elements; cache-bust bumped to `9.32.0`.
- `src/athena/api/static/dashboard.js` — `qualityBand`, `riskBand`,
  `buildExecutiveSummaryLines`, `renderExecutiveSummary`; extended
  `renderCockpitGauges`/`resetCockpitGauges`; `renderDecisionBrief`'s hero
  section rebuilt as Decision Banner + Executive Summary.
- `src/athena/api/static/dashboard.css` — `.decision-banner` (+ stance
  variants), `.executive-summary-list`, `.hero-metric-band`, 4-column
  gauge grid; removed the now-dead `.decision-brief-thesis` rule.
- `tests/api/platform/test_dashboard_hosting.py` — new assertions for every
  new element/function.
- `docs/MILESTONES.md` — new "ATHENA UX Overhaul" tracked section (UX-1
  through UX-9); this log.

### Public APIs

- None — pure frontend restructuring, no backend/API surface touched.

### Validation and architecture

- Full regression: **1016 passed** (unchanged — no backend files touched).
- No Ruff/mypy scope (no `.py` files changed).
- JS brace/paren balance checked against the pre-edit baseline (added code
  perfectly balanced; the single pre-existing off-by-one paren count
  unchanged). Live server restart + isolated-browser console-error check:
  zero errors on load.
- ADR-005 preserved: Executive Summary lines are either exact counts or
  engine-authored explanation strings, never generated. No ADR required —
  no domain object, contract, or backend behavior changed.

### Risks and technical debt

- I could not exercise the redesigned cockpit end-to-end myself (no owner
  credentials) — needs an owner click-through.
- Holding-period and strategy-name gaps are now documented (not silently
  missing) — worth a decision on whether to scope small backend additions
  for them in a future UX milestone.
- No new technical debt beyond the above.

### Remaining work

- **Owner smoke test**: select a TRADE, WATCH, and NO_TRADE decision each;
  confirm the band words (score/confidence quality word, risk hazard word)
  look sensible against the raw numbers; confirm the Decision Banner's
  color/border matches the stance; confirm the Executive Summary's 5 lines
  read naturally and match what's shown elsewhere on the same brief;
  confirm Expected R:R shows `—` for a non-TRADE decision with no trade plan.
- Next in the UX Overhaul program: **UX-2** (score/confidence/risk
  storytelling — star-rated contributors, "why ATHENA trusts this"
  checklist, risk category summary, safety-gate checklist, "Why?" button).

### Commit message

```text
feat(dashboard): add Hero Decision Card, Executive Summary, Decision Banner

- Add qualityBand/riskBand: band composite score, confidence, and risk into words (Weak-Excellent / Low-Medium-High) alongside the existing raw numbers, colored via the existing gauge tone logic
- Add a 4th cockpit gauge for Expected R:R, read directly from trade_plan.risk_reward
- Replace the plain thesis paragraph with a colored Decision Banner (reusing the existing stance palette) and a 5-line Executive Summary composed entirely from already-persisted engine explanations, never generated
- Research-confirm holding-period and strategy-name (from the owner's UX audit example) don't exist prospectively anywhere in the backend; omit rather than fabricate, flagged for a future milestone
```

---

## Decisions & Trace UI overhaul (READY FOR REVIEW)

| | |
|---|---|
| Completed | 2026-07-25 |
| Objective | Owner-reported: the Decisions & Trace tab was overcrowded (13 sections stacked in one scroll), had redundant gate chips (list card vs. brief), and a Reasoning Trace DAG that duplicated the brief's own analysis in a side panel. Also fixed: logging out left the browser URL on the previous tab, so the next login reopened it instead of defaulting to Portfolio Overview. |
| Scope | Full frontend redesign: outcome-grouped horizontal carousels for Today's Decisions, a sticky cockpit header with live score/confidence/risk gauges, a four-tab Decision Brief (Setup/Analysis/Context/Response), and a Reasoning Trace that navigates to the matching tab instead of duplicating it. Plus the logout navigation fix. No backend/API changes. |
| Tests | Full suite **1016 passed** (2 stale dashboard-hosting assertions updated to match the new static markup, plus new assertions for every redesigned element); no backend files touched, so no Ruff/mypy scope. No JS test runner in this repo — verified via full-suite substring assertions, a JS brace/paren balance check against the pre-edit baseline, and a live browser console-error check (zero errors on load) |
| Coverage | Frontend-only change; no Python coverage impact |
| Status | **READY FOR REVIEW** — first-pass redesign smoke-tested live by owner (2026-07-26), four issues found and fixed in a follow-up pass (below); needs a second owner click-through |
| Branch | feature/live-dashboard |

### Fix pass (2026-07-26, owner screenshots)

Owner smoke-tested the first pass live and reported four issues, all fixed:

- **Empty state didn't actually hide** — filtering to zero matching
  decisions left the cockpit gauges (`0.0`/`0.0`/`0.0`), all four tabs, and
  the action buttons visibly rendered and interactive, with the title
  ellipsis-truncated to "Instrument Decisio…". Root cause: the browser's
  built-in `[hidden] { display: none }` default is author-overridable, and
  `.decision-brief-gauges`/`.decision-brief-tabstrip`/`.decision-brief-actionbar`
  each had their own unconditional `display: grid`/`flex` rule, which wins
  the cascade over the UA default even with the `hidden` attribute present.
  Fixed with explicit `[hidden] { display: none; }` overrides for all
  three, a short "Select a symbol" placeholder that fits without
  truncating, and `resetCockpitGauges()` now also runs in the empty state
  for defense-in-depth.
- **Carousel nav arrows/fade showed even with nothing to scroll** — Trade's
  single-card row still showed both chevrons and a hard-clipped right edge.
  Added `wireCarouselOverflow()`: measures actual overflow per row via
  `ResizeObserver` + a scroll listener, toggling `.scrollable`/`.at-start`/
  `.at-end` classes so each arrow only appears when there's somewhere to
  scroll *in that direction*, and a `mask-image` edge fade (instead of the
  earlier gradient-on-button approach, which read as a hard clip) shows
  only on the side that actually has more content.
- **Repetitive, undifferentiated gate notes** — many Watch/No-trade cards
  showed the identical muted-gray "N of M gates open" with no at-a-glance
  severity cue (only a hover tooltip). Added a `tone-good-text`/
  `tone-warn-text`/`tone-bad-text` color cue (0 / 1-2 / 3+ failed gates)
  reusing the existing tone-text convention, so severity reads at a glance
  across a row of cards without hovering each one.
- **Possible stray character before a card's score digits** — traced the
  render path (`decisionScoreValue` → `extractScoreFromText` →
  `renderDeckCard`); no currency symbol or prefix is ever added to the raw
  `.toFixed(1)` score string, so this is almost certainly a screenshot
  compression artifact on a thin-serif numeral, not a real bug — flagged to
  the owner to double-check live rather than "fixed" speculatively.

### Scope completed

- **Logout navigation fix**: `logoutBtn`'s click handler never reset the
  browser URL, so it stayed at e.g. `/dashboard/decisions`; the next login's
  `initializeRoute()` read that stale path and reopened the same tab instead
  of defaulting to Portfolio Overview. Fixed with one
  `window.history.replaceState({tabId: "overview"}, "", "/dashboard/overview")`
  call before the reload/unlock-gate branch.
- **Outcome-grouped carousels** (`renderDecisionCarousels`, `renderDeckCard`,
  `DECISION_CAROUSEL_SECTIONS`): Today's Decisions is grouped into
  Trade → Watch → No trade → Insufficient data (any other `decision_type`
  gets its own carousel too, so nothing is ever silently hidden), always in
  that priority order regardless of timestamp (owner-confirmed). Each
  section is an independently scrollable horizontal row with prev/next
  buttons, expanded by default (owner-confirmed), collapsible via its
  header. Cards are compact (symbol, score, time, a single "N of M gates
  open" note whose tooltip lists the specific failing gates — the full
  breakdown lives in the Analysis tab, so nothing shown before is now
  unreachable). `decisionTypePriority()` drives both the display order and
  the default-selected decision on load/filter-change, replacing the old
  "newest first" fallback.
- **Sticky cockpit header**: symbol, stance chip, decision-type chip,
  as-of time, and Re-validate button, plus three live gauges (composite
  score / confidence / risk) that read the exact same
  `analysisPresentation()`-derived value/level already computed for the
  Analysis tab's summary cards (`renderCockpitGauges`) — never a second,
  independently-derived number. Always visible regardless of scroll
  position or active tab.
- **Four-tab Decision Brief** (`switchBriefTab`, `activeBriefTab`) replaces
  the old 13-section stacked scroll: **Setup** (eligibility, TradePlan,
  intraday chart), **Analysis** (score/confidence/risk depth, "why not a
  trade", safety & quality gates), **Context** (decision timeline, session/
  market context, analytical provenance), **Response** (your response/
  outcome, similar past setups). Every one of the original sections is
  preserved — none dropped, only regrouped — and every existing loader
  (`loadDecisionDepth`, `loadDecisionContext`, `loadDecisionChart`,
  `loadJournalPanel`, `loadDecisionAnalogs`, `loadDecisionCounterfactual`,
  `loadDecisionPlanFreshness`) is unchanged, since each still targets the
  same element ids, now nested inside a tab pane instead of a flat section.
  `activeBriefTab` deliberately persists across decision switches — flipping
  through several decisions to compare the same aspect keeps you on that
  aspect instead of resetting to Setup each time (graceful selection).
- **Action bar and tab strip are static, wired once**: the header
  previously rebuilt and rebound its action buttons on every
  `renderDecisionBrief` call; since it's now a fixed part of the sticky
  header (not rebuilt per decision), the buttons are wired exactly once at
  load and read `activeDecisionData`/`activeDecisionId` at click time — this
  needed a new `resetActionButtons()` so a "Removed" state from a previous
  symbol can't leak onto the next one.
- **Reasoning Trace navigates instead of duplicating**: clicking a DAG node
  now looks up its tab via a new `STAGE_TAB_MAP` and calls `switchBriefTab`,
  so the brief opens exactly where that value lives. The side panel
  (`showStageDetails`) now shows only what isn't duplicated elsewhere — the
  stage's status and provenance references — instead of re-rendering the
  same score/confidence/risk/regime/trade-plan content a second time.
  Removed the now-dead `renderStageDetailBody`, `renderContextStageBody`,
  `renderTradePlanStageBody`, and `refreshSelectedStageDetail` (their output
  is fully covered by the brief tabs, which have no async-refresh problem
  since they're rebuilt fresh on every `renderDecisionBrief`).
- **Text truncation handled throughout**: long symbols/labels get
  `text-overflow: ellipsis` plus a `title` tooltip with the full value
  (deck card symbol, cockpit symbol, gauge labels, carousel hint text,
  decision-note tooltips, DAG node names) — nothing silently clips without
  a way to read the full value.

### Files created

- None (all additive/restructuring within existing files).

### Files modified

- `src/athena/api/static/index.html` — replaced the 3-column
  `.trace-workstation` with a toolbar card, outcome-carousel container, and
  a 2-column workstation (Decision Brief | Reasoning Trace); new static
  cockpit header (identity, gauges, tab strip, action bar); cache-bust
  bumped to `9.30.0`.
- `src/athena/api/static/dashboard.js` — see Scope completed above for the
  full list of new/changed functions; `logoutBtn` click handler.
- `src/athena/api/static/dashboard.css` — new carousel/cockpit/tab-strip/
  gauge styles; removed dead `.briefing-*` and DAG-panel-duplication rules.
- `tests/api/platform/test_dashboard_hosting.py` — replaced stale
  DAG-duplication assertions with new ones for the redesigned elements;
  fixed two assertions that checked `js` for id attributes now emitted only
  in static `html`.
- This log.

### Public APIs

- None — pure frontend restructuring, no backend/API surface touched.

### Validation and architecture

- Full regression: **1016 passed** (unchanged count — no backend files
  touched, no new backend tests needed).
- No Ruff/mypy scope (no `.py` files changed).
- JS has no linter/test runner in this repo; verified via (1) full-suite
  substring assertions against the new markup/functions, (2) a brace/paren
  balance check of the whole file against the pre-edit baseline (added code
  is perfectly balanced; the single pre-existing off-by-one paren count is
  unchanged, confirmed not something this change introduced), (3) a live
  server restart + isolated-browser console-error check (zero errors on
  load, both `dashboard.css`/`dashboard.js` served 200).
- No order-placement path touched. ADR-005 preserved: gauges/tabs render
  already-computed values, nothing generated. No ADR required — no domain
  object, contract, or backend behavior changed.

### Risks and technical debt

- I could not exercise the redesigned Decisions & Trace tab end-to-end
  myself (no owner credentials) — the live console-error check only covers
  the pre-login page. **This milestone needs an owner click-through in the
  real dashboard before being marked approved.**
- No new technical debt beyond the above; dead code from the old DAG-panel
  duplication was removed rather than left in place.

### Remaining work

- **Owner smoke test round 2** (see chat for step-by-step): re-check the
  empty state (filter to zero matches) now cleanly shows just "Select a
  symbol" with no gauges/tabs/actions visible; confirm the Trade row (or
  any single-card row) shows no nav arrows and no clipped edge; confirm
  Watch/No-trade cards now show a color-coded gate note; confirm the
  ADANIENSOL-like score glyph looks correct live. Beyond the fix pass: the
  original round-1 smoke test items (carousel order, gauges, all four tabs,
  DAG node jumps, logout landing on Portfolio Overview) plus the owner's
  own list of further refinements are still pending.

### Commit message

```text
refactor(dashboard): overhaul Decisions & Trace UI; fix logout tab reset

- Replace the flat, chronological Today's Decisions list with outcome-grouped horizontal carousels (Trade/Watch/No trade/Insufficient data), always in that priority order regardless of timestamp
- Add a sticky cockpit header with live score/confidence/risk gauges, replacing the 13-section stacked scroll with a four-tab brief (Setup/Analysis/Context/Response) — every original section preserved, just regrouped
- Make Reasoning Trace nodes navigate to the matching brief tab instead of duplicating its content in a side panel; remove the now-dead duplicate renderers
- Fix logout leaving the browser URL on the previous tab, which made the next login reopen it instead of defaulting to Portfolio Overview
- Fix empty-state gauges/tabstrip/actionbar not actually hiding ([hidden] was overridden by an unconditional display rule); hide carousel nav arrows/fade when a row doesn't overflow; add a quick-glance severity color to repetitive gate notes
```

---

## M-X3 — Confidence-decay clock (APPROVED)

| | |
|---|---|
| Completed | 2026-07-25 |
| Objective | Replace the dashboard's ad-hoc client-side Active/Expired TradePlan badge (computed from an un-quantified `new Date()` comparison) with a real, quantified, backend-computed decay percentage and band (FRESH/AGING/STALE/EXPIRED) over the plan's validity window |
| Scope | New read-only `/plan-freshness` endpoint + a decay badge next to the existing TradePlan validity row |
| Tests | Full suite **1016 passed** (+3 new); changed-file Ruff clean; mypy clean on touched modules |
| Coverage | Existing project coverage retained; no separate percentage collected |
| Status | **APPROVED** (owner smoke confirmed 2026-07-25) |
| Branch | feature/live-dashboard |

### Scope completed

- Added `DecisionsService.get_trade_plan_freshness(decision_id, as_of=None)`:
  pure arithmetic over the decision's already-persisted
  `TradePlan.valid_from`/`valid_until` and an `as_of` instant (defaults to
  wall-clock `datetime.now(tz=timezone.utc)` at the API boundary — the same
  "genuine wall-clock read for a real-time question, not an analytical
  computation" precedent already used by `record_trade_outcome`'s
  `closed_ts`). No domain object, engine, or persisted report touched.
- Added two new config thresholds to `config/decision.json`'s `plan` block:
  `freshness_warn_fraction` (0.5) and `freshness_stale_fraction` (0.8) —
  the elapsed-fraction bands that separate FRESH → AGING → STALE, with
  `EXPIRED` once `as_of >= valid_until`. Validated ordered (`warn <
  stale`) via a `model_validator`, matching the existing
  `DecisionThresholdsCfg._ordered` pattern.
- Added `TradePlanFreshnessDTO` (frozen, `Decimal` decay_fraction) and
  `GET /api/v1/decisions/{id}/plan-freshness?as_of=<optional ISO8601>` —
  the optional query param lets a caller ask "what would freshness look
  like at time X", defaulting to right now.
- Added a small `plan-freshness-badge` next to the pre-existing
  `.plan-status` (Active/Expired/Pending) badge in the TradePlan card,
  filled in asynchronously once the endpoint resolves (e.g. "62% decayed"),
  color-banded FRESH→green, AGING→blue, STALE→amber, EXPIRED→red. The
  pre-existing client-side Active/Expired/Pending badge is left untouched —
  this milestone adds the quantified decay signal alongside it rather than
  replacing already-working, already-tested behavior. Cache-busted
  dashboard assets to `9.29.0`.
- No architecture change: pure read-only arithmetic over already-persisted
  `TradePlan` fields and new (additive) config thresholds — no domain
  object, contract, or frozen model touched; no new Protocol method needed.

### Files created

- None (all additive to existing files).

### Files modified

- `config/decision.json`, `src/athena/config/models.py`
  (`DecisionPlanCfg.freshness_warn_fraction`/`freshness_stale_fraction` +
  ordering validator)
- `src/athena/api/v1/dtos/{decisions,__init__}.py` (`TradePlanFreshnessDTO`)
- `src/athena/api/v1/services/decisions_service.py`
  (`get_trade_plan_freshness`, `_freshness_summary` helper)
- `src/athena/api/v1/routers/decisions.py` (`GET .../plan-freshness`)
- dashboard CSS/JS/HTML; `tests/api/v1/test_core_apis.py`,
  `tests/api/platform/test_dashboard_hosting.py`; `docs/MILESTONES.md`;
  this log.

### Public APIs

- Added `GET /api/v1/decisions/{decision_id}/plan-freshness`.
- Added two new required config fields to `config/decision.json`'s `plan`
  block (backward-incompatible for hand-edited config files missing them —
  acceptable since `config/decision.json` is the single owner-controlled
  instance, already updated in this change set).
- No frozen domain object, calculation, risk policy, or order boundary
  changed.

### Validation and architecture

- Full regression: **1016 passed** (was 1013; +3 net new — no-trade-plan,
  four-band decay-via-as_of, and not-found tests).
- Ruff clean on every touched file (one pre-existing, unrelated F811 —
  duplicate `SizingConfig` class in `config/models.py` — spotted while
  running the check; flagged separately as out-of-scope cleanup, not
  touched here).
- mypy clean on all touched modules.
- ADR-005 preserved: the decay badge and summary are arithmetic/template
  composition over persisted values and config, never generated text.
- No order-placement path touched. Determinism, replayability, provider
  independence preserved. No ADR required — additive config fields + a
  read-only endpoint over existing persisted fields.

### Risks and technical debt

- The endpoint reads live `config/decision.json` thresholds at request
  time, same intentional trade-off as M-X2's counterfactual: answers "what
  would it take right now," not "what it looked like at scoring time."
- The pre-existing client-side Active/Expired/Pending badge and the new
  backend-computed decay badge are two independent, not-necessarily-in-sync
  signals (one reads the browser's clock, one reads the server's). Both are
  derived from the same `valid_from`/`valid_until`, so they should agree in
  practice, but a large client/server clock skew could show a mismatch.
  Acceptable for v1; worth consolidating onto the backend signal only in a
  future pass if it ever causes confusion.
- No new technical debt beyond the above.

### Remaining work

- Owner smoke: open a decision with a trade plan, confirm the new decay
  badge shows a sensible percentage next to the existing status badge, and
  that it transitions through FRESH → AGING → STALE color bands as time
  passes (or via a shortened `validity_hours` in config for faster manual
  testing).
- Next in the Intraday Edge Program: **M-X8** (synthetic canary decision),
  **M-X9** (config-change impact preview), or **M-X10** (outcome-tagged
  setups) are all clean, no-gate candidates. **ADR-006** (circuit-limit
  risk signal) still awaits owner sign-off before M-X4 can start.

### Commit message

```text
feat(api): add deterministic TradePlan decay clock (M-X3)

- Add get_trade_plan_freshness: quantifies elapsed/remaining/decay_fraction over the plan's persisted valid_from/valid_until window against an as_of instant (defaults to wall-clock now)
- Add freshness_warn_fraction/freshness_stale_fraction config thresholds to config/decision.json, ordered-validated like existing DecisionThresholdsCfg
- Add GET /api/v1/decisions/{id}/plan-freshness and a decay-percentage badge next to the existing TradePlan status badge, replacing nothing — purely additive alongside the already-working client-side Active/Expired indicator
```

---

## M-X2 — "Why not" counterfactual (APPROVED)

| | |
|---|---|
| Completed | 2026-07-25 |
| Objective | For every non-TRADE decision, quantify the exact score/confidence/risk/evidence/market gap to the TRADE gate — pure arithmetic over already-persisted values and current config thresholds, never a recomputed decision |
| Scope | New read-only `/counterfactual` endpoint + Decision Brief "Why not a trade?" section |
| Tests | Full suite **1013 passed** (+3 new); changed-file Ruff clean; mypy clean on touched modules |
| Coverage | Existing project coverage retained; no separate percentage collected |
| Status | **APPROVED** (owner smoke confirmed 2026-07-25) |
| Branch | feature/live-dashboard |

### Scope completed

- Added `DecisionsService.get_decision_counterfactual(decision_id)`: for a
  TRADE decision, returns a trivial "already cleared" result. For any other
  decision type, reads the decision's own persisted `gate_results` (never
  recomputed) plus its persisted score/confidence/risk report (via the
  existing `_fetch_report` helper) and the live `config/decision.json`
  thresholds, then computes, per failing gate, `current`, `required`, and
  `gap = max(0, required - current)` (or `current - required` for RISK,
  since risk is a ceiling not a floor). Composite score gap is computed the
  same way against `min_composite_for_trade`.
- Handles the two non-numeric blockers that are not expressed as a
  `QualityGate` at all — `Direction.NONE` (no trend direction) and a missing
  `trade_plan` (ATR/SMA indicators unavailable) — by checking the decision's
  own persisted `direction`/`trade_plan` fields directly, only when no
  numeric gate/score gap remains, so a decision is never told to "close a
  gap" that isn't actually the reason it wasn't a TRADE.
- Added `CounterfactualGapDTO`/`DecisionCounterfactualDTO` (frozen, `Decimal`
  fields) and a deterministic `summary` string (e.g. `"To become a TRADE:
  score +4.20, confidence +10.00."`) built from simple template composition
  over the computed gaps — no generated rationale, per ADR-005.
- Added `GET /api/v1/decisions/{id}/counterfactual`.
- Added a "Why not a trade?" Decision Brief section (after "Score ·
  confidence · risk", before "Safety & quality gates"): an "all gates
  cleared" chip for TRADE decisions, or a row per gap (current vs. required,
  with a gap chip) plus the summary sentence for everything else. Cache-
  busted dashboard assets to `9.28.0`.
- No architecture change: pure read-only arithmetic over already-persisted
  data and existing config thresholds — no domain object, contract, or
  frozen model touched; no new Protocol method needed (reuses
  `get_decision`/`_fetch_report`).

### Files created

- None (all additive to existing files).

### Files modified

- `src/athena/api/v1/dtos/{decisions,__init__}.py` (`CounterfactualGapDTO`,
  `DecisionCounterfactualDTO`)
- `src/athena/api/v1/services/decisions_service.py`
  (`get_decision_counterfactual`, `_decimal_or_none`, `_market_quality_value`,
  `_counterfactual_summary` helpers)
- `src/athena/api/v1/routers/decisions.py` (`GET .../counterfactual`)
- dashboard CSS/JS/HTML; `tests/api/v1/test_core_apis.py`,
  `tests/api/platform/test_dashboard_hosting.py`; `docs/MILESTONES.md`;
  this log.

### Public APIs

- Added `GET /api/v1/decisions/{decision_id}/counterfactual`.
- No frozen domain object, calculation, risk policy, or order boundary
  changed.

### Validation and architecture

- Full regression: **1013 passed** (was 1010; +3 net new — already-TRADE,
  confidence/risk gap quantification, and non-numeric direction-blocker
  tests).
- Ruff clean on every touched file. mypy clean on all touched modules.
- ADR-005 preserved: summary is template composition over persisted/
  computed numbers, never generated text.
- No order-placement path touched. Determinism, replayability, provider
  independence preserved. No ADR required — read-only arithmetic over
  existing persisted fields and existing config thresholds.

### Risks and technical debt

- Thresholds are read live from `config/decision.json` at request time; if
  the owner changes a threshold between when a decision was scored and when
  its counterfactual is viewed, the gap reflects the *current* threshold,
  not the one in force at scoring time. This is intentional (answers "what
  would it take right now"), but worth stating explicitly since it's the one
  place this milestone reads live config rather than only persisted data.
- No new technical debt beyond the above.

### Remaining work

- Owner smoke: open a WATCH/NO_TRADE decision, confirm the gap numbers and
  summary sentence match the persisted score/confidence/risk shown
  elsewhere on the same Decision Brief; open a TRADE decision, confirm the
  "all gates cleared" state.
- Next in the Intraday Edge Program: **M-X3 confidence-decay clock** (clean,
  no gate) is the natural follow-on. **ADR-006** (circuit-limit risk signal)
  still awaits owner sign-off.

### Commit message

```text
feat(api): add "why not a trade" counterfactual gap for decisions

- Add get_decision_counterfactual: quantifies exact score/confidence/risk/evidence/market gap to the TRADE gate from already-persisted gate_results and report values, plus live config thresholds
- Handle non-numeric blockers (no direction, no trade plan) only when no numeric gate/score gap remains, so a decision is never told to close a gap that isn't the real reason
- Add GET /api/v1/decisions/{id}/counterfactual and a "Why not a trade?" Decision Brief section with per-gate gap rows and a deterministic summary sentence
```

---

## M-X1 — Historical analog matcher (APPROVED)

| | |
|---|---|
| Completed | 2026-07-25 |
| Objective | Deterministic nearest-neighbor retrieval of past decisions with a similar score/confidence/risk fingerprint, each with its logged human response and realized outcome (now real, thanks to M-X0) |
| Scope | New read-only `/analogs` endpoint + Decision Brief "Similar past setups" section |
| Tests | Full suite **1010 passed** (+2 new); changed-file Ruff clean; mypy clean on touched modules |
| Coverage | Existing project coverage retained; no separate percentage collected |
| Status | **APPROVED** (owner smoke confirmed 2026-07-25) |
| Branch | feature/live-dashboard |

### Scope completed

- Added `DecisionProvider.list_recent_decisions(limit)` — a raw, unfiltered
  read (newest first) for analytical queries that need a candidate pool
  rather than a paginated/filtered API listing. Implemented in both
  `SqliteDecisionProvider` (delegates to `repo.list_decisions`) and
  `InMemoryDecisionProvider`.
- Added `DecisionsService.get_decision_analogs(decision_id, limit=5)`:
  extracts the target decision's (score composite, confidence overall, risk
  overall) fingerprint from its persisted report — refactored the existing
  report-lookup logic out of `get_decision_depth`/`get_decision_context`
  into a shared `_fetch_report` helper rather than duplicating it a third
  time — then computes Euclidean distance against every other persisted
  decision with a comparable (status `OK`) fingerprint, grouping by
  `run_id` to fetch each run's detail once rather than once per decision.
  Decisions with an `UNKNOWN` score/confidence/risk (including the target
  itself, if unassessed) are excluded from comparison entirely — never
  compared against a fabricated or defaulted value.
- Each returned match carries its logged `DecisionJournalEntry.user_action`
  and `TradeOutcome.pnl`/`closed_ts` if present (via M-X0's `get_journal_entry`/
  `get_trade_outcome`) — `null` when never recorded, never inferred.
- Added `GET /api/v1/decisions/{id}/analogs?limit=1..20`.
- Added a "Similar past setups" Decision Brief section: each match shows
  symbol, stance chip, an intuitive similarity % (derived client-side from
  distance for display only — never persisted or compared), a response
  chip, and a pnl chip (color-coded) or "no outcome logged". Rows are
  clickable and jump to that decision, matching the existing Decision
  Timeline row pattern. Cache-busted dashboard assets to `9.27.0`.
- No architecture change: pure read-only composition over already-persisted
  data (Decision, DecisionReport.machine, DecisionJournalEntry, TradeOutcome)
  via one small additive Protocol method — no domain object, contract, or
  frozen model touched.

### Files created

- None (all additive to existing files).

### Files modified

- `src/athena/api/v1/providers/{base,sqlite_providers,in_memory}.py`
  (`list_recent_decisions`)
- `src/athena/api/v1/dtos/{decisions,__init__}.py` (`DecisionAnalogDTO`,
  `DecisionAnalogsDTO`)
- `src/athena/api/v1/services/decisions_service.py` (`get_decision_analogs`,
  shared `_fetch_report`/`_fingerprint` helpers, refactored
  `get_decision_depth`/`get_decision_context` to reuse `_fetch_report`)
- `src/athena/api/v1/routers/decisions.py` (`GET .../analogs`)
- dashboard CSS/JS/HTML; `tests/api/v1/test_core_apis.py`,
  `tests/api/platform/test_dashboard_hosting.py`; `docs/MILESTONES.md`;
  this log.

### Public APIs

- Added `GET /api/v1/decisions/{decision_id}/analogs`.
- No frozen domain object, calculation, risk policy, or order boundary
  changed.

### Validation and architecture

- Full regression: **1010 passed** (was 1008; +2 net new — ranking/exclusion
  test and an unknown-fingerprint-target test).
- Ruff clean on every touched file (one import-sort auto-fix applied,
  verified no behavior change via full suite re-run).
- mypy clean on all touched modules.
- ADR-005 preserved: analog matches are factual retrieval from persisted
  data, no generated text, no recomputed comparison.
- No order-placement path touched. Determinism, replayability, provider
  independence preserved. No ADR required — additive Protocol method only.

### Risks and technical debt

- Candidate pool is capped at the 500 most recent decisions (matching the
  existing `SqliteDecisionProvider` windowing convention) — a very long
  history could miss older analogs. Acceptable for v1; revisit if the
  journal grows large enough for this to matter in practice.
- Similarity % is a display-only derived value (linear map from Euclidean
  distance over a fixed 0–173.2 range) — not a statistically calibrated
  confidence measure. Documented as such in the UI copy ("factual retrieval
  only, nothing generated").
- No new technical debt beyond the above.

### Remaining work

- Owner smoke: select a decision with several historical siblings, confirm
  the ranking looks sensible, confirm decisions without a persisted
  fingerprint (or with UNKNOWN score/confidence/risk) are excluded, confirm
  clicking a row navigates to that decision's brief.
- Next in the Intraday Edge Program: **M-X2 "Why not" counterfactual** or
  **M-X3 confidence-decay clock** (both clean, no gate). **ADR-006**
  (circuit-limit risk signal) still awaits owner sign-off.

### Commit message

```text
feat(api): add historical analog matcher for decisions

- Add DecisionProvider.list_recent_decisions for raw candidate-pool reads, implemented in both Sqlite and InMemory providers
- Add get_decision_analogs: deterministic nearest-neighbor retrieval by score/confidence/risk fingerprint, excluding any decision without a comparable persisted assessment
- Refactor report-lookup logic shared across depth/context/analogs into one _fetch_report helper instead of duplicating it a third time
- Add GET /api/v1/decisions/{id}/analogs and a "Similar past setups" Decision Brief section showing each match's logged response and realized outcome
```

---

## M-X0 — Decision Journal & Outcome capture (APPROVED)

| | |
|---|---|
| Completed | 2026-07-25 |
| Objective | Close a foundational gap discovered while designing the Intraday Edge Program: `DecisionJournalEntry` and `TradeOutcome` are fully modeled, persisted, and already consumed by M10.4 AI Playbook Diagnostics — but nothing in the codebase ever called `save_journal_entry`. The feedback loop has been silently empty since M10.4 shipped. |
| Scope | Owner accept/reject/ignore response + realized-outcome logging, server-computed pnl/holding-time/TradePlan-adherence, new Decision Brief section |
| Tests | Full suite **1008 passed** (+19 new); changed-file Ruff clean; mypy clean on touched modules |
| Coverage | Existing project coverage retained; no separate percentage collected |
| Status | **APPROVED** (owner smoke confirmed 2026-07-25 — response recording, persistence across reload, outcome pnl/adherence computation all verified) |
| Branch | feature/live-dashboard |

### Scope completed

- Discovered via `git grep`-level tracing (no code written yet) that
  `save_journal_entry` — the repository method that persists the owner's
  response to a decision — is called nowhere in `src/`. `TradeOutcome` had
  no persistence path at all (no repository methods, no table). M10.4's
  `PlaybookDiagnosticsAnalyzer.analyze(journal=...)` has therefore always
  received an empty sequence in production. This is the first milestone of
  the AI-proposed "Intraday Edge Program" (`docs/MILESTONES.md`), reordered
  ahead of the originally-planned Historical Analog Matcher (M-X1) once
  discovered, since analog matching over always-empty outcomes would have
  been hollow.
- Added `trade_outcomes` SQLite table (schema v6→v7) and repository methods
  `save_trade_outcome`/`get_trade_outcome`/`list_trade_outcomes`, plus
  `get_journal_entry` (single-decision lookup; only `list_journal` existed).
  Additive only — no existing table/method changed.
- Extended `DecisionProvider` Protocol (P8.3 API-layer abstraction, not an
  ATHENA-002 §7 analytical contract) with
  `save_journal_entry`/`get_journal_entry`/`save_trade_outcome`/
  `get_trade_outcome`; implemented in both `SqliteDecisionProvider` and
  `InMemoryDecisionProvider`.
- Added `POST/GET /api/v1/decisions/{id}/journal` and
  `POST/GET /api/v1/decisions/{id}/outcome`. PnL (`entry`/`exit` vs.
  `Decision.direction`), holding time (`closed_ts - decision.ts`), and
  TradePlan adherence (`entered_within_zone`, `hit_stop`, `hit_target`) are
  computed server-side from the persisted `TradePlan` — never client-
  supplied, so every outcome is deterministic and explainable (ADR-005).
  Write endpoints require `Permission.EXECUTE`; reads require `READ`.
- Added a "Your response" section to the Decision Brief: Accept/Reject/
  Ignore buttons with optional notes, and — once accepted — an outcome-
  logging form (entry/exit/quantity only; everything else computed) that
  becomes a read-only result card (PnL, adherence chips, holding time) once
  logged. Cache-busted dashboard assets to `9.26.0`.
- No architecture change: `DecisionJournalEntry`/`TradeOutcome` were already
  frozen domain objects; `journal` is already a named contract row in
  ATHENA-002 §7's module table (consumes `decisions`, produces "persisted
  journal rows") — this milestone completes what the blueprint already
  specified, per the R6 anti-scope-creep guardrail checked before starting.

### Files created

- None (all additive to existing files).

### Files modified

- `src/athena/data/store/{schema,serialization,repository}.py` (trade_outcomes
  table + methods, `get_journal_entry`)
- `src/athena/api/v1/providers/{base,sqlite_providers,in_memory}.py` (Protocol
  extension + two implementations)
- `src/athena/api/v1/dtos/{decisions,__init__}.py` (4 new DTOs)
- `src/athena/api/v1/services/decisions_service.py` (record/get journal +
  outcome, server-side pnl/adherence computation)
- `src/athena/api/v1/routers/decisions.py` (4 new endpoints)
- dashboard CSS/JS/HTML; `tests/api/v1/test_core_apis.py`,
  `tests/data_layer/test_decision_journal.py`,
  `tests/runtime/test_dry_run_schedule.py` (schema-version bump fix),
  `tests/api/platform/test_dashboard_hosting.py`; `docs/MILESTONES.md`; this log.

### Public APIs

- Added `POST/GET /api/v1/decisions/{decision_id}/journal`,
  `POST/GET /api/v1/decisions/{decision_id}/outcome`.
- No frozen domain object, calculation, risk policy, or order boundary
  changed — `DecisionJournalEntry`/`TradeOutcome` were already defined;
  this milestone only adds their persistence and a real entry point.

### Validation and architecture

- Full regression: **1008 passed** (was 1004; +19 net new: 2 API tests +
  4 repository round-trip tests + updated 2 stale schema-version assertions
  + assorted dashboard-hosting assertions).
- Ruff clean on every touched file; 3 pre-existing `SIM117` findings in
  `repository.py` (nested `with` in unrelated pre-existing methods) left
  untouched per scope discipline.
- mypy clean on all touched modules.
- ADR-005 preserved: pnl/holding-time/adherence are computed once, server-
  side, from persisted data — never entered by the owner, never
  recalculated by the UI.
- No order-placement path touched. Determinism, replayability, provider
  independence preserved. No ADR required (confirmed against ATHENA-002
  §19/§7 before starting — see Scope completed).

### Risks and technical debt

- Outcome logging currently supports one outcome per decision (upsert by
  `decision_ref:closed_ts`); partial exits across multiple fills are not
  modeled. Acceptable for v1 — no existing UI/data assumed multiple
  outcomes either.
- `adherence` is a fixed 2-key computed dict (`entered_within_zone`,
  `hit_stop`, `hit_target`) when a TradePlan exists, empty otherwise (e.g.
  outcome logged against a non-TRADE decision). Documented, not silently
  defaulted.
- No new technical debt beyond the above.

### Remaining work

- Owner smoke: unlock the live workstation, select an ACCEPTED-worthy
  decision, record Accept/Reject/Ignore, confirm it persists across a
  reload, log a realized outcome and confirm pnl/adherence compute
  correctly, confirm a REJECTED/IGNORED decision does not show the outcome
  form.
- Next in the Intraday Edge Program: **M-X1 Historical analog matcher**,
  now genuinely valuable once real journal/outcome data accumulates.
  **ADR-006** (circuit-limit risk signal) still awaits owner sign-off.

### Commit message

```text
feat(data): wire Decision Journal and Trade Outcome to a real owner action

- Add trade_outcomes table (schema v7) and repository persistence — TradeOutcome existed in the frozen domain model with zero persistence path until now
- Extend DecisionProvider with journal/outcome save+get, implemented in both Sqlite and InMemory providers
- Add POST/GET journal and outcome endpoints; pnl, holding time, and TradePlan adherence are computed server-side, never client-supplied (ADR-005)
- Add a "Your response" Decision Brief section: accept/reject/ignore + outcome logging, closing the gap where M10.4 AI Playbook Diagnostics ran against an always-empty journal since it shipped
```

---

## M-D4 — Context lane (APPROVED)

| | |
|---|---|
| Completed | 2026-07-25 |
| Objective | Ground each selected decision in session/calendar awareness, persisted regime/market-health context, and owner-curated external research links; add a deterministic Decision Brief export |
| Scope | Session/calendar context, persisted regime/market-health surfacing, deterministic brief export, approved external links |
| Tests | Full suite **1004 passed** (+15 new); changed-file Ruff clean; mypy clean on touched modules |
| Coverage | Existing project coverage retained; no separate percentage collected |
| Status | **APPROVED** (owner approved 2026-07-25, after live smoke-test review and fixes) |
| Branch | feature/live-dashboard |

### Scope completed

- Extended `ScanCapture` and `DecisionReportingEngine.report()` with optional
  `regime`/`market_health` fields, persisting them into `DecisionReport.machine`
  the same additive way M-D3 persisted score/confidence/risk — no frozen
  domain object changed, no new architecture. Wired both call sites
  (`scanner.py`, `owner_validation.py`) so future scans/re-validates persist
  real regime/market-health context instead of leaving it unrecorded.
- Added a new owner-maintained `config/external_links.json` (+ pydantic model
  + loader), mirroring the existing `calendar/events.json` convention:
  static, provenance-tagged link metadata only (title/url/source/added_by/
  date_added), keyed by instrument id or `GLOBAL`. No fetching, no scraping,
  no news ingestion.
- Added authenticated, read-only `GET /api/v1/decisions/{decision_id}/context`
  combining a live-computed `CalendarContext` (session type, hours, holiday,
  weekly/monthly expiry, scheduled events) with the persisted regime/
  market-health snapshot and matching external links (GLOBAL, exact
  instrument id, or bare-symbol fallback).
- Added a deterministic `DECISION_BRIEF` export artifact type, composing
  already-persisted Decision + Depth + Context DTOs into one JSON/Markdown/
  Text artifact via the existing Export & Presentation pipeline (P6.6/P8.4).
  No new export dependency; no recomputation.
- Added a "Session & market context" section to the Instrument Decision Brief
  dashboard pane: session/expiry/holiday chips, regime labels, market-health
  dimensions, curated external links, and an "Export Brief" action that
  downloads the artifact client-side.
- **Owner smoke UI fixes** (post-review): redesigned the Session & market
  context card with semantic color-coded chips (good/bad/warn/neutral/unknown
  by label meaning), block-card styling, and icons per section; dropped the
  redundant raw prose duplicating the market-health dimension chips. Fixed
  `risk_reward` bypassing `formatDecisionPrice` in the TradePlan card (now a
  proper `formatDecisionRatio` helper, 2dp). Fixed the Decision Trace DAG's
  Trade Plan node showing full, un-rounded `Decimal` tails (e.g.
  `2.0000000000000000001`) in its human-readable trace summary — root cause
  was `DecisionEngine._trace()` interpolating raw `Decimal` values into the
  `trade_plan` stage summary string; fixed by reusing the engine's existing
  `_fmt_score` quantize-to-2dp helper (presentation-only; no `TradePlan`
  value, gate, or contract changed). Also fixed the DAG detail panel
  mislabeling every `ref_ids` reference list as "N rules checked" regardless
  of stage type.
- **Reasoning Trace DAG complete redesign** (post-review, systemic): the same
  overflowing-Decimal complaint applied to every node, not just Trade Plan —
  `scoring/engine.py`, `confidence/engine.py`, and `risk/engine.py` each
  interpolated raw division-derived `Decimal`s (composite/overall scores,
  dimension averages, cross-engine spread, contradiction deltas) straight
  into their `explanation=` strings; `regime/engine.py` and
  `sector_health/engine.py` interpolated raw SMA averages into their trend
  explanations. Added a local 2dp quantize helper to each of the first three
  (mirroring `decision/engine.py`'s existing `_fmt_score`) and inline `:.2f`
  specifiers to the latter two — presentation-only, no stored value, gate,
  or contract changed. Separately, redesigned the DAG node detail cards to
  stop rendering raw trace prose at all for Regime/Market Health/Score/
  Confidence/Risk/Trade Plan: they now reuse the *same* already-fetched,
  already-formatted structured data the Decision Brief panel uses
  (`/depth` and `/context` responses, cached client-side as `activeDepth`/
  `activeContextData`/`activeDecisionData`) — color-coded chips for Regime/
  Market Health, the existing `renderAnalysisSummaryCard` for Score/
  Confidence/Risk, and the existing TradePlan formatters for Trade Plan.
  Handles the load-order race (trace loads independently of depth/context)
  by re-rendering the currently-selected node once the richer data arrives.
  Also fixed the provenance grid's misleading "N rules checked" label
  (applied to every stage regardless of type — those are reference IDs, not
  rules) to "N reference(s)". Evidence/Decision/Sector Health nodes without
  a structured secondary source still show prose, now from the corrected
  backend explanation strings. Cache-busted dashboard assets to `9.24.0`.
- **Re-validate moved to the Decision Brief header** (owner feedback: "no
  idea of where it exists"): added `#decision-brief-revalidate-header`
  next to the "as of" timestamp in the static header (always visible
  regardless of scroll position), removed the old button buried at the
  bottom of the "Human next step" actions row. Wired once at page load
  (not per-render, since the header markup is static) referencing the
  cached `activeDecisionData` at click time so it always targets the
  currently-selected instrument. Enabled/disabled alongside brief load/
  empty state. Added `.btn-sm` and made `.decision-brief-header` an
  explicit flex container (previously relied on `align-items`/
  `justify-content` with no `display: flex` — dead CSS, now fixed).
  Cache-busted dashboard assets to `9.25.0`.
- **Owner smoke fix**: found and fixed a pre-existing latent bug in the P8.4
  Export layer, surfaced for the first time by repeated Decision Brief
  exports in one browser session. `ExportsService` was constructed fresh per
  HTTP request, so its `ExportPresentationEngine`'s id counter reset to zero
  every time — every export got id `exp-0001`, and the in-memory artifact
  store's oldest-first lookup silently kept returning the *first* export
  ever created that session regardless of which decision was actually
  exported. Fixed by injecting one long-lived `ExportPresentationEngine`
  singleton (`dependencies._export_engine`) instead of constructing a new
  one per request; added a regression test exporting two different
  decisions in sequence and asserting distinct ids/payloads.

### Files created

- `config/external_links.json`
- `src/athena/api/v1/services/decision_brief.py`
- `tests/api/v1/test_decision_context_service.py`

### Files modified

- `src/athena/scanner/models.py`, `src/athena/reporting/engine.py`,
  `src/athena/scanner/scanner.py`, `src/athena/ops/owner_validation.py`
  (regime/market-health persistence);
- `src/athena/config/models.py`, `src/athena/config/loader.py` (external
  links config);
- `src/athena/api/v1/dtos/{decisions,base,__init__}.py`,
  `src/athena/api/v1/services/decisions_service.py`,
  `src/athena/api/v1/routers/decisions.py`, `src/athena/api/dependencies.py`
  (context endpoint);
- `src/athena/export/{models,engine}.py`,
  `src/athena/api/v1/services/exports_service.py` (Decision Brief export);
- dashboard CSS/JS/HTML; reporting/config/API/dashboard tests; milestone
  roadmap; this implementation log.

### Public APIs

- Added `GET /api/v1/decisions/{decision_id}/context`. Response contains
  `calendar`, `regime`, `market_health`, and `external_links` blocks; regime/
  market-health render `UNKNOWN` explicitly when not yet persisted for a
  decision (pre-M-D4 decisions, until re-validated).
- Added `SourceArtifactType.DECISION_BRIEF` to the export request contract;
  `POST /api/v1/exports` now accepts it and composes a deterministic brief
  from already-persisted data only.
- No frozen domain object, calculation, risk policy, or order boundary
  changed. `DecisionReportingEngine.report()` and `ScanCapture` gained
  optional, backward-compatible parameters only.

### Validation and architecture

- Full regression: **1003 passed** (was 989 at M-D3; +14 net new tests).
- Ruff clean on every touched file; pre-existing unrelated lint debt in
  `config/models.py`, `export/engine.py`, `reporting/engine.py`, and
  `test_reports_analytics_export.py` (outside this milestone's diff) was left
  untouched per scope discipline.
- mypy clean on all touched modules.
- ADR-004 preserved: no new dashboard dependency/framework.
- ADR-005 preserved: context/regime/market-health render only persisted data;
  the export composes persisted DTOs verbatim, never recomputes.
- CalendarEngine remains the sole trading-day authority (R-3); no new
  calendar logic was added, only surfaced.
- No order-placement path touched. Determinism, replayability, provider
  independence preserved. No ADR or schema migration required.

### Risks and technical debt

- Decisions created before this milestone show `regime`/`market_health` as
  `UNKNOWN` until re-validated — identical, already-accepted precedent from
  M-D3's score/confidence/risk backfill behavior.
- `load_external_links_file` treats a missing `external_links.json` as an
  empty list rather than failing loudly, since the file is new and owner-
  optional; every other config loader in this project fails loudly on a
  missing file. This one deliberate exception should be called out in
  owner review.
- No new technical debt beyond the above.

### Remaining work

- None. Owner smoke completed live (Session & market context, regime/
  market-health persistence via re-validate, `config/external_links.json`
  entry surfacing, Export Brief download, Reasoning Trace DAG node cards,
  header Re-validate placement) — every issue found during smoke testing
  was fixed and re-verified in this milestone (see additional entries
  above). Approved 2026-07-25.
- **Instrument decision brief track closed.** M-D5 (News Evidence) remains
  deferred until DD-5/provider approval; no successor milestone is queued.

### Commit message

```text
feat(dashboard): add M-D4 context lane, regime persistence, and brief export

- Persist regime/market-health into ScanCapture and DecisionReport.machine, mirroring M-D3's score/confidence/risk pattern
- Add owner-curated config/external_links.json with GLOBAL/instrument/bare-symbol matching, no fetching or news ingestion
- Add GET /api/v1/decisions/{id}/context combining live calendar context, persisted regime/market-health, and curated links
- Add deterministic DECISION_BRIEF export artifact composing Decision + Depth + Context DTOs via the existing export pipeline
- Add dashboard Session & market context section and Export Brief download action, cache-busted to 9.22.0
```

---

## M-D3 — ATHENA analytical depth (APPROVED)

| | |
|---|---|
| Completed | 2026-07-24 |
| Objective | Explain eligibility and analytical depth for each selected decision |
| Scope | Eligibility, score/confidence/risk detail, timeline, safe candidate removal |
| Tests | Full suite **989 passed**; focused M-D3 **36 passed**; changed-file Ruff; browser JS compile |
| Coverage | Existing project coverage retained; no separate percentage collected |
| Status | **APPROVED** (owner approved, 2026-07-25) |
| Branch | develop |

### Scope completed

- Persisted each scanner-produced `DecisionReport.machine` in the originating
  run detail, retaining score, confidence, risk, evidence, indicator, and trace
  provenance without adding analytical computation to the API or dashboard.
- Closed the owner-validate analytical gap: confidence, risk, evidence, and
  market-health stages now run before DecisionEngine so re-validate persists
  real depth instead of UNKNOWN confidence/risk refs.
- Extended report serialization with source-created explanations and
  contributions for score, confidence, and risk dimensions per ADR-005.
- Added authenticated, read-only
  `GET /api/v1/decisions/{decision_id}/depth`, backed by the provider protocol
  and deterministic in-memory/SQLite implementations.
- Added typed depth DTOs for the originating universe eligibility assessment
  and persisted score/confidence/risk artifacts; unavailable historical depth
  is reported explicitly as `UNKNOWN`.
- Added Decision Brief sections for universe eligibility/rules, collapsible
  score-confidence-risk components, and the latest eight persisted decisions
  for the selected instrument.
- Redesigned score/confidence/risk as progressive disclosure: recognizable
  summary cards with 0–100 meters, followed by full-width category and component
  drill-downs with aligned values and recorded inputs.
- Added confirmed candidate removal from both Decision Brief and Market
  Intelligence. Removal stops future validation only; decisions, traces, and
  replay evidence remain untouched.
- Retained after-hours Re-validate behavior from M-D2 and cache-busted
  dashboard assets to `9.21.0`.

### Files created

- None.

### Files modified

- Decision report/run-detail persistence; decision DTO/provider/service/router;
  dashboard CSS/JS/HTML; API, reporting, owner-validation, and hosting tests;
  milestone roadmap; this implementation log.

### Public APIs

- Added `GET /api/v1/decisions/{decision_id}/depth`.
- Response contains `eligibility`, `score`, `confidence`, and `risk` blocks
  sourced exclusively from persisted artifacts.
- No frozen domain object, calculation, risk policy, or order boundary changed.

### Validation and architecture

- Full regression: **989 passed**.
- Focused reporting/owner-validation/decision/dashboard/trace tests:
  **36 passed**.
- Changed Python files pass Ruff; the modern browser runtime compiled
  `dashboard.js` (`9.20.0`) successfully.
- ATHENA-002 report boundary preserved: API and dashboard render only.
- ADR-005 preserved: explanations/contributions originate in analytical
  modules and are persisted, never reconstructed by UI.
- Candidate deletion does not cascade to immutable decision/run history.
- Determinism, replayability, provider independence, and no-order boundary
  preserved. No ADR or schema migration required.

### Risks and technical debt

- Decisions created before M-D3 have no persisted report payload and therefore
  show `UNKNOWN` analytical depth until the symbol is re-validated.
- Timeline is bounded to the API's existing 5,000-decision retrieval window and
  displays the latest eight entries per instrument.
- No new technical debt introduced.

### Remaining work

- Owner smoke: unlock after host restart, re-validate one symbol, inspect
  eligibility/components/timeline, and optionally verify confirmed removal.
- M-D4 (Context lane) design started 2026-07-25 against existing calendar,
  export, and regime/market-health contracts.

### Commit message

```text
feat(dashboard): expose persisted decision depth

- Persist score, confidence, risk, and eligibility rationale for faithful rendering
- Add decision depth API, analytical drill-down, and per-symbol decision timeline
- Preserve decision history when removing candidates from future validation
```

---

## M-D2 follow-up — After-hours validate as_of (APPROVED)

| | |
|---|---|
| Completed | 2026-07-24 |
| Objective | Make Validate / Re-validate usable overnight without pretending stale quotes are live |
| Scope | Calendar-aware `as_of` clamp + explicit session-close UI messaging |
| Tests | Targeted resolve/dashboard/candidates **15 passed** |
| Status | **APPROVED** — owner smoke confirmed after-hours session-close validation |
| Branch | develop |

### Scope completed

- Added pure `resolve_validate_as_of`: during known session → live `now`;
  after close / premarket / weekend / holiday / Muhurat-without-timings → last
  completed session close from CalendarEngine (R-3).
- Wired into `POST /api/v1/market/validate` and CLI `validate-symbols` when
  `--as-of` is omitted; explicit CLI `--as-of` remains an override.
- Response now includes `as_of` + `as_of_mode` (`live` | `session_close`).
- Dashboard Validate / Re-validate toasts explain session-close analysis and
  replace raw FRESHNESS ingest-reject text with an actionable message.
- Unattended cycle worker `as_of` is unchanged (separate concern).

### Files created

- `src/athena/calendar/resolve_as_of.py`
- `tests/unit/test_resolve_validate_as_of.py`

### Files modified

- Calendar package export, candidates service/DTO, symbol_validate result,
  CLI validate-symbols, dashboard JS/HTML assets `9.19.3`, hosting regression,
  milestone roadmap, this log.

### Validation

- Targeted: **15 passed**.
- Architecture: CalendarEngine remains sole trading-day authority; no silent
  live pretence after hours; no order-placement path touched.

---

## M-D2 — Intraday chart + TradePlan overlays (APPROVED)

| | |
|---|---|
| Completed | 2026-07-24 |
| Objective | Ground each Decision Brief in persisted intraday price context without prediction |
| Scope | Provider-independent candles API, SVG candlesticks, TradePlan overlays, explicit freshness |
| Tests | Full suite **980 passed**; targeted M-D2 **20 passed**; changed-file Ruff; HTML parse |
| Coverage | Existing project coverage retained; no separate percentage collected |
| Status | **APPROVED** — owner smoke confirmed charts and session-close validation |
| Branch | develop |

### Scope completed

- Added authenticated read-only
  `GET /api/v1/market/instruments/{instrument_id}/candles` for persisted
  `1m`/`5m`/`15m` OHLCV, chronological ordering, bounded `limit`, and explicit
  `FRESH`/`STALE`/`NO_DATA` status.
- Added `CandleHistoryProvider` with deterministic in-memory and live SQLite
  implementations; the service maps canonical `Candle` objects without
  coupling the API to Kite/FileProvider.
- Freshness uses `validation.json`’s
  `freshness.intraday_max_minutes_behind`; service clock is injectable and the
  threshold boundary is unit-tested.
- Added a dependency-free responsive SVG candlestick chart in the selected
  Instrument Decision Brief using the most recent 120 persisted 5-minute bars.
- Overlaid the persisted TradePlan entry zone, invalidation/stop, and targets;
  no chart-derived or invented price level is created.
- Added explicit stale-data warning (“Re-validate before using the TradePlan”),
  no-data and unavailable states, OHLCV hover tooltips, price/time axes, source,
  latest timestamp, and bar count.
- Added bare-symbol → `NSE:` fallback for older decisions while preserving
  canonical instrument IDs when present.
- Dashboard assets cache-busted to `9.19.0`.

### Files created

- `src/athena/api/v1/services/market_history_service.py`
- `tests/api/v1/test_market_history.py`

### Files modified

- API app/dependencies, market DTO/router, provider protocols and in-memory/
  SQLite providers, dashboard HTML/CSS/JS, API test fixture, hosting regression,
  milestone roadmap, and this implementation log.

### Public APIs

- Added `GET /api/v1/market/instruments/{instrument_id}/candles`.
- Query: `timeframe=1m|5m|15m`, `limit=1..500`.
- Response is read-only and includes candles plus freshness metadata.
- No frozen domain object or analytical contract changed.

### Validation and architecture

- Full regression: **980 passed**.
- Targeted market-history/core/dashboard tests: **20 passed**.
- All changed Python files pass Ruff; dashboard HTML parses successfully.
- Modern browser loaded `9.19.0` assets; authenticated owner chart interaction
  remains the final manual smoke step.
- ADR-004 preserved: no new chart dependency/framework; SVG is static vanilla
  JS over the localhost API.
- ADR-005 preserved: chart renders persisted price/TradePlan data only.
- Determinism, replayability, provider independence, explainability, and
  no-order boundary are preserved. No ADR required.

### Risks and technical debt

- The chart is historical context from the latest persisted ingest, not a
  streaming quote chart; freshness state makes this explicit.
- Bare-symbol fallback assumes NSE for legacy decisions; current canonical IDs
  bypass the fallback.
- Full analytical score/confidence/risk payloads remain M-D3 scope.
- No technical debt introduced.

### Suggested improvements and remaining work

- Owner smoke: select a symbol with ingested 5m candles; verify bars, tooltip,
  freshness badge, and exact TradePlan overlay values.
- M-D3 only after approval: eligibility narrative, symbol decision timeline,
  and resolvable analytical depth.
- News remains deferred to M-D5/DD-5.

### Commit message

`feat(dashboard): add freshness-aware intraday decision chart`

---

## M-D1 — Instrument Decision Brief foundation (APPROVED)

| | |
|---|---|
| Completed | 2026-07-24 |
| Objective | Turn a selected Today’s Decision into a disciplined, explainable stock brief |
| Scope | Full decision detail, TradePlan strip, safety gates, provenance, daily dismiss, re-validate/MI actions |
| Tests | Full suite **976 passed**; targeted dashboard/API **17 passed**; HTML parse; changed-test Ruff |
| Coverage | Existing project coverage retained; no separate percentage collected |
| Status | **APPROVED 2026-07-24** — owner smoke verified |
| Branch | develop |

### Scope completed

- Added a responsive three-pane Decisions workstation: Today’s Decisions,
  selected Instrument Decision Brief, and existing Reasoning Trace DAG.
- Selecting a card now calls the existing `GET /api/v1/decisions/{id}` endpoint
  as well as the trace endpoint, with stale-response guards for rapid selection.
- Renders persisted explanation, stance/type/score chips, all gate rationales,
  score/confidence/risk provenance references, and exact as-of time in IST.
- Renders persisted `TradePlan` entry zone, invalidation/stop, targets, R:R,
  model sizing/risk, validity interval, and active/pending/expired state.
- WATCH/PASS/INSUFFICIENT decisions explicitly show that no actionable plan is
  authorized; the UI never invents entry/exit values.
- Added non-destructive **Dismiss today** per instrument using an IST-day
  browser key, visible hidden count, and Restore action. Decisions, traces,
  journal, and replay evidence are never deleted.
- Added Re-validate and Market Intelligence actions using existing paths.

### Files created

- None.

### Files modified

- `src/athena/api/static/index.html`
- `src/athena/api/static/dashboard.css`
- `src/athena/api/static/dashboard.js`
- `tests/api/platform/test_dashboard_hosting.py`
- `tests/api/v1/test_core_apis.py`
- `docs/MILESTONES.md`
- `IMPLEMENTATION_SUMMARY.md`

### Public APIs

- No new API or frozen domain contract. M-D1 reuses the existing decision
  detail/trace and market validate APIs.

### Validation and architecture

- Full regression: **976 passed**.
- Targeted dashboard hosting + core API: **17 passed**.
- Changed Python tests pass Ruff; dashboard HTML parses successfully.
- Modern browser loaded the `9.18.0` assets and exposed the new brief landmark;
  interactive owner-data verification remains an owner smoke step after unlock.
- ADR-004 preserved: static HTML/CSS/vanilla JS and localhost FastAPI only.
- ADR-005 preserved: the UI renders stored rationale and never reconstructs or
  generates post-hoc explanations.
- Determinism, replayability, provider independence, and no-order boundary
  remain unchanged. No ADR required.

### Risks and technical debt

- Daily dismiss is intentionally local to one browser profile; it is not a
  cross-device preference and does not affect future candidate validation.
- Score/confidence/risk are provenance references only because rich analytical
  payloads are not yet persisted/resolvable. M-D3 owns that depth.
- The local Node executable is too old to parse pre-existing optional chaining;
  browser execution plus hosting assertions cover this milestone.
- No technical debt introduced beyond the approved phased limits.

### Suggested improvements and remaining work

- Owner smoke: unlock, select TRADE/WATCH/PASS cards, verify plan/no-plan,
  dismiss/restore, re-validate, and responsive layout.
- M-D2 subsequently delivered the read-only candles endpoint and chart overlays.
- News remains deferred to M-D5/DD-5 and is not represented as available data.

### Commit message

`feat(dashboard): add explainable instrument decision brief`

---

## Decisions pagination / latest-per-instrument fix (READY FOR REVIEW)

| | |
|---|---|
| Completed | 2026-07-24 |
| Objective | Stop Today’s Decisions from silently truncating after the first API page |
| Scope | Walk all `/api/v1/decisions` pages before client dedupe; enlarge SQLite list window |
| Tests | `tests/api/platform/test_dashboard_hosting.py` asserts page-walk helpers; decisions paging suite unchanged |
| Status | **READY FOR REVIEW** |
| Branch | develop |

- Dashboard previously called `/api/v1/decisions` with the default `page_size=20`, then
  deduped only that page — large validate/seed runs hid most symbols.
- `fetchAllDecisionPages()` now requests `page_size=100`, `sort_by=ts`, and follows
  `pagination.has_next` (capped at 50 pages) before `latestDecisionPerInstrument()`.
- SQLite decision provider window raised from 2000 → 5000 so page walking can surface
  Nifty-scale candidate sets.
- Cache-bust dashboard assets `?v=9.17.0`. Hard-refresh after deploy.

---

## Live Entry M-E5 — hardening & ops polish (APPROVED)

| | |
|---|---|
| Completed | 2026-07-24 |
| Objective | Harden the approved Dock/URL → unlock → Kite → LIVE workstation path |
| Scope | Login throttling; production JWT secret resolution; localhost/TLS controls; final runbook and roadmap |
| Tests | Owner QA: **976 passed, 127 warnings in 9.53s**; auth/serve **33 passed**; R1 smoke **3 passed** |
| Coverage | Existing project coverage gate retained; no separate percentage collected |
| Status | **APPROVED 2026-07-24** — professional live-entry track complete |
| Branch | develop |

### Scope completed

- Added deterministic, thread-safe login throttling per normalized
  username/client IP: five failures in ten minutes trigger a fifteen-minute
  lockout, HTTP 429, and `Retry-After`.
- Replaced the known development JWT signing key for owner-configured runtime:
  explicit `ATHENA_JWT_SECRET` wins; otherwise a stable SHA-256 key is derived
  from the bcrypt owner hash without exposing that hash as the signing key.
- Changed the transport default to `127.0.0.1`; added paired
  `--ssl-certfile`/`--ssl-keyfile` serve options and an optional mkcert recipe.
- Preserved the existing AuthService audit sink, `/auth/me` profile,
  read-only Kite boundary, cycle-runner advisory lock, and launchd role for
  unattended scheduling.
- Added `docs/ops/LIVE_ENTRY.md`, `.env.example` security controls, README
  linkage, and M-E1–M-E5 roadmap entries.
- Isolated the R1 file-backed smoke from live Nifty seeding by disabling the
  network seed in its temporary config and adding only fixture candidates
  `AAA`/`BBB`.
- Added `docs/ops/QA_VERIFICATION.md` as the canonical regression, targeted
  suite, warning-triage, manual acceptance, and evidence procedure.

### Files created

- `src/athena/api/security/login_limiter.py`
- `tests/api/v1/test_login_limiter.py`
- `docs/ops/LIVE_ENTRY.md`
- `docs/ops/QA_VERIFICATION.md`

### Files modified

- API configuration, app wiring, security exceptions/exports/error mapping,
  auth router, serve CLI, auth route tests, `.env.example`, README,
  `scripts/smoke_file_backed_day.sh`, `docs/MILESTONES.md`, and this
  implementation log.

### Public APIs and compatibility

- No frozen analytical/domain contract changed.
- Existing `/api/v1/auth/login` now additionally returns RFC-style HTTP 429
  while locked; successful response and token contracts are unchanged.
- `athena serve` adds optional TLS flags; HTTP localhost remains the default.

### Validation and architecture

- Determinism/replayability: analytical execution paths are untouched; limiter
  clock is injectable and unit-tested.
- ADR compliance: no ADR required. The in-process worker remains interactive;
  launchd remains the unattended scheduler. No embedded UI framework added.
- Provider independence and no-order boundary: unchanged.
- Owner full regression on macOS Darwin 25.2.0 / Python 3.14.6:
  **976 passed, 127 warnings in 9.53s**.
- Known warning categories are Starlette/httpx TestClient deprecation, PyJWT's
  short test-only signing key, and Starlette's HTTP 422 constant rename; new
  categories/count increases require investigation.
- R1 file-backed smoke: **3 passed** after fixture isolation.
- Changed-file Ruff: passed. Repository-wide Ruff still reports 243 pre-existing
  findings outside this milestone; no new changed-file finding remains.
- Shell launchers parse successfully; macOS `Info.plist` validates.

### Risks, debt, and remaining work

- Login counters are intentionally process-local; restarting the localhost
  workstation clears a lockout. This is proportionate for a single-user,
  localhost-only app and avoids introducing persistent auth state.
- Optional TLS is a terminal power-user mode; the Dock launcher intentionally
  keeps the default trusted localhost HTTP path.
- No technical debt or architecture drift introduced by M-E5.
- Remaining work: none; owner approved M-E5 on 2026-07-24.

### Consolidated commit message

`feat(ops): deliver professional live-entry workstation`

QA follow-up: `test(ops): isolate smoke and document QA verification`

---

## Live Entry M-E4 — macOS Dock launcher (APPROVED)

| | |
|---|---|
| Completed | 2026-07-24 |
| Scope | Thin native `.app` wrapper; one-command installer; health-aware server start and browser open |
| Tests | App plist/executable, shell syntax, temporary signed app installation; full suite **970 passed** |
| Status | **APPROVED** |
| Branch | develop |

- `./install-athena-app` installs an ad-hoc-signed `~/Applications/ATHENA.app`.
- Dock click opens an already-running workstation or starts `./athena-serve --with-cycles`, waits for `/health/live`, then opens the dashboard.
- Finder-safe PATH includes Apple Silicon / Intel Homebrew; failures show a native alert and point to `artifacts/logs/athena-serve.log`.
- The app contains no secrets—only the repository path—and remains a shell app bundle per ADR-004 (no Tauri/Qt/Electron).
- Documentation: README quick entry and `HOST_SCHEDULE.md` install/Dock/reinstall instructions.

---

## Live Entry M-E3 — in-UI Kite morning gate (APPROVED)

| | |
|---|---|
| Completed | 2026-07-24 |
| Scope | Verify Kite session after unlock; browser login URL; request-token exchange and live reinjection |
| Tests | Full suite: **966 passed**; Kite service/API tests; HTML parse; Python lint |
| Status | **APPROVED** |
| Branch | develop |

- Routes: `GET /api/v1/ops/kite/status`, `POST /kite/start-auth`, `POST /kite/complete-auth`.
- Gate verifies read-only Kite `/user/profile`; missing/expired sessions block the LIVE state.
- Owner opens Kite in a new tab, pastes redirect URL/request token, then ATHENA exchanges, persists, re-injects, and verifies the token.
- API secret and access token never return to the browser; start/complete require ADMIN.
- CLI `./kite-auth` remains the fallback. Dashboard assets `?v=9.15.0`.
- File-backed smoke now forces its intended `file` provider instead of inheriting the owner's live Kite config.
- Header **KITE** button shows live session state; opens reconnect panel; **Clear Session** drops the access token via `POST /api/v1/ops/kite/disconnect` (assets `?v=9.16.0`).

---

## Live Entry M-E2 — athena serve supervisor (APPROVED)

| | |
|---|---|
| Completed | 2026-07-24 |
| Scope | One-command localhost host: API + optional due-cycle worker; health serve fields; cycle lock |
| Tests | `tests/ops/test_serve_runtime.py`; `tests/api` health compatibility |
| Status | **APPROVED** |
| Branch | develop |

- CLI: `athena serve [--host] [--port] [--with-cycles] [--cycle-interval] [--open]`.
- Wrappers: `./athena-serve`, `./athena-daily serve`.
- Worker reuses `_execute_run_due` / `HostDueRunner` (same path as `run-due`).
- Advisory lock `artifacts/locks/cycle-runner.lock` shared with `run-due`.
- Health: `kite_token_status`, `cycles_enabled`, `last_cycle`, `serve_error`.
- Dashboard badge reflects cycles / kite presence (`?v=9.14.0`).

---

## Live Entry M-E1 — Auth surface + unlock screen (APPROVED)

| | |
|---|---|
| Completed | 2026-07-24 |
| Scope | Wire AuthService to HTTP; owner seed from `.env`; unlock gate; Bearer + refresh in dashboard |
| Tests | `tests/api/v1/test_auth_routes.py` + `tests/api` (120 passed) |
| Status | **APPROVED** |
| Branch | develop |

- Routes: `GET/POST /api/v1/auth/status|login|refresh|logout|me`.
- Owner seed: `ATHENA_OWNER_USER` + `ATHENA_OWNER_PASSWORD_HASH`; CLI `athena set-owner-password`.
- When owner hash is set, `ATHENA_SINGLE_USER` bypass is disabled; unlock is required.
- Dashboard: unlock overlay, sessionStorage JWTs, Bearer on `apiRequest`, refresh on 401, SSE `access_token` query, profile from `/me`.
- `/` redirects to `/dashboard/`. Assets `?v=9.13.0`.

---

## Dashboard workspace usability improvements (READY FOR REVIEW)

| | |
|---|---|
| Completed | 2026-07-24 |
| Scope | Balanced Portfolio layout; dedicated searchable/scrollable MI stock list; Add & validate; known VIX regime selection; Decisions filters |
| Tests | HTML parse; `tests/api/v1/test_owner_candidates.py` (5 passed); browser layout/filter/scroll verification |
| Status | **READY FOR REVIEW** |
| Branch | develop |

- Overview: holdings and charts now share the left stack while log-fill/pools/reset stay on the right, removing the empty center gap; holdings retain a sticky, independently scrolling table and per-row **Add & validate**.
- MI candidate list: dedicated Stock List card with a 561-symbol independently scrolling region, live search/count, and per-row **Validate/Remove**; validation results scroll separately.
- MI dashboard picks the newest regime and prefers non-UNKNOWN volatility when merging runs.
- Decisions: Stance / Type / Sort controls (newest, symbol, score, stance) plus search.
- Assets `?v=9.12.0`. Hard-refresh after deploy. Validation card scrolls as one panel; stock-list search uses transparent dark styling.

---

## Regime VIX snapshot + decision UX clarity (READY FOR REVIEW)

| | |
|---|---|
| Completed | 2026-07-24 |
| Scope | Persist India VIX market snapshot on ingest (fixes VOLATILITY_UNKNOWN); human-friendly decision copy + chip UI |
| Tests | `tests/data_layer/test_ingestion.py` (snapshot persist); decision/ops suites |
| Status | **READY FOR REVIEW** |
| Branch | develop |

- Live ingest now writes `market_snapshot()` (includes India VIX) into the ledger when the provider supports it.
- Owner validation fills VIX from INDIA VIX candles when snapshot VIX is missing.
- DecisionEngine explanations use plain language (Buy/Hold/Pass) with rounded scores and named safety checks.
- Decisions + Qualified Today: stance chips (BUY/HOLD/PASS), score chip, “Needs Risk/Data/…” gate chips; MI volatility badge shows High/Low/Normal/Unknown.
- Dashboard assets `?v=9.9.0`. Re-run validate/smoke after upgrade so new explanations and VIX appear.

---

## On-demand symbol validate + Decisions UI fix (READY FOR REVIEW)

| | |
|---|---|
| Completed | 2026-07-24 |
| Scope | After MI Add, run scoped kite ingest+score so the symbol appears in Eligible/Excluded and Decisions; fix Decisions search-icon overlap; dedupe latest decision per symbol |
| Tests | `tests/api/v1/test_owner_candidates.py` (validate empty body 422) |
| Status | **READY FOR REVIEW** |
| Branch | develop |

- `POST /api/v1/market/validate` + `CandidatesService.validate_candidates` → `ops/symbol_validate.validate_symbols`.
- MI **Add & validate** button: upsert candidate then validate; refreshes Market Intelligence panels.
- CLI: `athena validate-symbols SYM…` / `./athena-daily validate SYM`.
- Decisions: flex search bar (no absolute icon overlap); list shows latest decision per instrument.
- Cache bust dashboard assets `?v=9.8.0`.

---

## Nifty 500 daily candidate seed (READY FOR REVIEW)

| | |
|---|---|
| Completed | 2026-07-24 |
| Scope | Once-per-day merge-unique seed of `owner_candidates` from official Nifty 500 constituents CSV |
| Tests | `tests/ops/test_candidate_seed.py`; schema v6 (`ops_meta`) |
| Status | **READY FOR REVIEW** |
| Branch | develop |

- Config: `config/candidate_seed.json` (`source: NIFTY500`, merge_unique, once_per_day).
- Fetch: NSE archives CSV (+ niftyindices fallback); optional `local_file` for offline/tests.
- Merge: inserts missing symbols only; never wipes manual adds or overwrites existing notes.
- Wired into `athena cycle`, `./athena-run-due`, and `athena seed-candidates`.
- SCHEMA_VERSION 6: `ops_meta` tracks last seed date. Seed failure warns and continues with existing list.

---

## Portfolio reset + owner validation list (READY FOR REVIEW)

| | |
|---|---|
| Completed | 2026-07-24 |
| Scope | D-P1 portfolio fill reset (open\|all + CONFIRM); D-V1–D-V3 owner candidate list with two-layer daily qualify (UniverseEngine → WATCH/TRADE) |
| Tests | `tests/api/v1/test_owner_portfolio.py`, `test_owner_candidates.py`, `tests/ops/test_owner_validation.py`; schema v5 asserts updated |
| Status | **READY FOR REVIEW** |
| Branch | develop |

- **D-P1:** `delete_owner_positions(scope=open|all)`; `POST /api/v1/portfolio/positions/reset` (ADMIN + typed `CONFIRM`); Overview UI gate; best-effort auto-backup before wipe.
- **D-V1:** SCHEMA_VERSION 5 `owner_candidates`; CRUD `/api/v1/market/candidates`; MI list editor; shared `SqliteCandidateStore` for API + CLI.
- **D-V2:** `OwnerValidationPipeline` on `athena cycle` / `./athena-run-due` runs `UniverseEngine` on candidates; ingest scoped to candidate symbols (kite catalog override when needed); MI shows real Eligible/Excluded; kite.json no longer faked as Eligible.
- **D-V3:** Eligible names scanned via `DailyMarketScanner` + DecisionEngine; decisions/traces persisted; MI “Qualified Today” = WATCH/TRADE for cycle day (same rows as Decisions tab).

Files created: `ops/owner_candidates.py`, `ops/owner_validation.py`, `api/v1/{dtos/market,routers/market,services/candidates_service}.py`, candidate/validation tests. Files modified: schema/repository, CLI + HostDueRunner, sqlite pipeline provider, dashboard static assets, dependencies/router, this log + milestones. No ADR; no order placement; journal/runs untouched by portfolio reset.

---

## Dashboard live data + owner fill ledger (READY FOR REVIEW)

| | |
|---|---|
| Completed | 2026-07-24 |
| Scope | Remove dashboard seed/demo data; serve Decisions + Market Intelligence from SQLite; owner-entered Kite/Groww fill ledger for Portfolio Overview |
| Tests | API + data_layer green; new `tests/api/v1/test_owner_portfolio.py`; decision-trace + dashboard-summary updated for empty/real data |
| Status | **READY FOR REVIEW** |
| Branch | develop |

- Dropped `seed_sample_data` from API startup; live app wires `SqliteDecisionProvider`, `SqlitePortfolioProvider`, `SqlitePipelineRunProvider` via `wire_sqlite_providers`.
- Decision traces return **stored** `DecisionTrace` stages only (no synthetic 7-stage DAG).
- SCHEMA_VERSION 4: `owner_positions` table; `POST /api/v1/portfolio/positions` + `.../close` for manual fills (symbol/qty/entry/exit); cash from `config/portfolio.json` `initial_cash` (`PortfolioConfig`).
- Market Intelligence: latest SQLite run context; falls back to `kite.json` symbols when run has no universe payload; honest empty copy when neither exists.
- Dashboard Overview form to log/close owner fills; no Kite holdings API (still blocked).
- **Hotfix:** `SqliteRepository` uses `check_same_thread=False` + `RLock` so FastAPI request threads can reuse the startup connection (fixes “Log fill” / tab query thread errors).
- **Hotfix:** Market Intelligence toast on empty runs — removed TDZ reference to `evidenceText` before declaration in `dashboard.js`.

Files created: `src/athena/api/v1/providers/sqlite_providers.py`, `config/portfolio.json`, `tests/api/v1/test_owner_portfolio.py`. Files modified: schema/serialization/repository, dependencies/app, decisions/portfolio/dashboard services + routers/DTOs, dashboard static assets, tests, this log. No ADR; no order placement; frozen Position/TradeOutcome contracts reused.

---

## Production readiness -- R6 Closing / Day-Summary Cycle (APPROVED)

| | |
|---|---|
| Completed | 2026-07-23 |
| Scope | Post-close `CLOSING` cadence + dry-run cycle; briefing day roll-up + journal prompts (Blueprint §8). |
| Tests | Cadence closing cases; briefing day_summary + journal prompt clear when journaled |
| Status | **APPROVED** — Owner approved 2026-07-23 |
| Branch | develop |

- `RunTrigger.CLOSING`; `scheduling.closing` (`run_at` default 15:45); `is_closing_due` / `due_triggers`.
- Dry-run + `run-due` / CLI `cycle --trigger closing` support CLOSING.
- Briefings include `day_summary` + `journal_prompts` for decisions lacking journal rows.

Files created: (none new top-level). Files modified: `config/scheduling.json`, `src/athena/domain/enums.py`, `src/athena/config/models.py`, `src/athena/scheduling/{cadence,dry_run,__init__}.py`, `src/athena/notifications/{models,builder,__init__}.py`, `src/athena/ops/scheduled_run.py`, `src/athena/cli.py`, `docs/*`, tests. Public APIs: `is_closing_due`, `BriefingJournalPrompt`, extended `DailyBriefing`. No ADR; no order methods.

---

## Production readiness -- R5 Host Schedule + Failure Alerts (APPROVED)

| | |
|---|---|
| Completed | 2026-07-23 |
| Scope | External launchd/cron invokes due cycles + brief; hard failures alert via file + webhook (DD-9). No embedded cron. |
| Tests | `tests/ops/test_host_ops.py` (file alert, webhook mock, idle path, failure alert, brief-after-cycle) |
| Status | **APPROVED** — Owner approved 2026-07-23 |
| Branch | develop |

- CLI `athena run-due` + root `./athena-run-due` (sources `.env` for launchd).
- `HostDueRunner` evaluates cadence, runs due PREMARKET/REFRESH, optional brief, alerts on `AthenaError`.
- `FailureAlertDispatcher`: `artifacts/alerts/` + `ATHENA_ALERT_WEBHOOK_URL` (fallback `ATHENA_WEBHOOK_URL`).
- Docs: `docs/ops/HOST_SCHEDULE.md` + launchd plist example; email SMTP still deferred.

Files created: `config/host_ops.json`, `src/athena/ops/{failure_alerts,scheduled_run}.py`, `athena-run-due`, `docs/ops/HOST_SCHEDULE.md`, `docs/ops/launchd/com.athena.run-due.plist.example`, `tests/ops/test_host_ops.py`. Files modified: `src/athena/config/{models,loader,__init__}.py`, `src/athena/cli.py`, `src/athena/ops/__init__.py`, `.env.example`, `docs/*`, `README.md`, `IMPLEMENTATION_SUMMARY.md`. Public APIs: `HostDueRunner`, `FailureAlertDispatcher`, `load_host_ops_config`, `athena run-due`. No ADR; localhost/secrets policy preserved; no order methods.

---

## Production readiness -- R4 Kite Live Provider Adapter (APPROVED)

| | |
|---|---|
| Completed | 2026-07-23 |
| Scope | Read-only Zerodha Kite `MarketDataProvider`; config-selected bind; FileProvider remains default; secrets in `.env` only. |
| Tests | Contract suite green via fake transport; unit tests for quotes/candles/snapshot/allowlist; owner live smoke: INFY ingest OK |
| Status | **APPROVED** — Owner approved 2026-07-23 (live smoke + runbook) |
| Branch | develop |

- `KiteProvider` + allowlisted GET-only `UrllibKiteTransport` (`/instruments*`, `/quote*` only — no order paths, no kiteconnect SDK).
- Config: `config/providers/kite.json`; `ingestion.provider` accepts `file` \| `kite` (default `file`).
- Factory `build_market_data_provider`; CLI ingest/cycle loads `.env` then resolves provider.
- Ops: `docs/ops/KITE_LIVE_DATA.md` (token refresh, enable steps, limits); root `./kite-auth` interactive helper.
- Instrument ids: `NSE:SYMBOL`. Snapshot: index LTPs + India VIX; breadth left 0.

Files created: `src/athena/data/providers/{kite_provider,kite_transport,factory}.py`, `src/athena/config/env.py`, `config/providers/kite.json`, `docs/ops/KITE_LIVE_DATA.md`, `tests/data_layer/test_kite_provider.py`, `tests/contract/test_kite_provider_contract.py`. Files modified: `src/athena/config/{models,loader,__init__}.py`, `src/athena/cli.py`, `src/athena/api/app.py`, `config/ingestion.json`, `.env.example`, `docs/*`, `IMPLEMENTATION_SUMMARY.md`, `README.md`. Public APIs: `KiteProvider`, `build_market_data_provider`, `load_kite_provider_config`, `load_dotenv`. No ADR; frozen Protocol unchanged; no order methods.

---

## Production readiness -- R3 DD-1 Live Vendor Decision (APPROVED)

| | |
|---|---|
| Completed | 2026-07-23 |
| Scope | Written DD-1 decision record: criteria matrix, candidate vendors, **Zerodha Kite Connect** accepted; **no adapter code**. |
| Tests | N/A (documentation milestone) |
| Status | **APPROVED** — Owner approved 2026-07-23 (existing Kite account; Groww for manual execution only) |
| Branch | develop |

- Created `docs/decisions/DD-1-broker-live-data-vendor.md` against ATHENA-002 §15 and ADR-002.
- Recommendation: **Zerodha Kite Connect** as first live provider for R4; FileProvider remains default/fallback; C2 deep history deferred to DD-10/accumulation.
- Explicit non-goals: no R4 code, no orders, no websocket (DD-2).

Files created: `docs/decisions/DD-1-broker-live-data-vendor.md`. Files modified: `docs/MILESTONES.md`, `docs/PRODUCTION_READINESS_ROADMAP.md`, `README.md`, `IMPLEMENTATION_SUMMARY.md`.

---

## Production readiness -- R2 Decision Journal Persistence (APPROVED)

| | |
|---|---|
| Completed | 2026-07-23 |
| Scope | Persist Decision/Trace/Journal in SQLite (schema v3); SqliteDecisionSummarySource for `athena brief`; smoke seeds decision → briefing OK. |
| Tests | Full suite green; new `tests/data_layer/test_decision_journal.py`; smoke asserts briefing status OK |
| Status | **APPROVED** — Owner approved 2026-07-23 |
| Branch | develop |

- SCHEMA_VERSION 3: `decisions`, `decision_traces`, `decision_journal` tables.
- Repository: `save_decision`, `get_decision`, `get_trace`, `list_decisions`, `save_journal_entry`, `list_journal`.
- `SqliteDecisionSummarySource` wired into CLI brief; briefings reach OK when runs + decisions exist.
- Smoke seeds a fixture WATCH after cycle until live cycle emits decisions.

Files created: `src/athena/notifications/decision_source.py`, `tests/data_layer/test_decision_journal.py`. Files modified: `schema.py`, `serialization.py`, `repository.py`, `notifications/__init__.py`, `cli.py`, smoke script, ops SOP, MILESTONES, roadmap, IMPLEMENTATION_SUMMARY. No ADR; frozen Decision contracts unchanged; no order APIs.

---

## Production readiness -- R1 File-backed Daily Ops SOP (APPROVED)

| | |
|---|---|
| Completed | 2026-07-23 |
| Scope | Written SOP for file-backed daily advisory use; executable mock-day smoke on fixtures; fix CLI AthenaConfig nesting for due/cycle/brief/diagnose. |
| Tests | smoke script PASS + `tests/ops/test_file_backed_daily_smoke.py` |
| Status | **APPROVED** — Owner approved 2026-07-23 |
| Branch | develop |

- Added `docs/ops/FILE_BACKED_DAILY_OPS.md` (prereqs, refresh CSVs, premarket/refresh CLI sequence, failure playbook, smoke checklist).
- Added `scripts/smoke_file_backed_day.sh` (temp config/DB, fixture FileProvider, health → due → cycle → brief → diagnose).
- Fixed Phase 10 CLI to read `cfg.base.*` / `cfg.market.*` correctly on `AthenaConfig`.

Files created: `docs/ops/FILE_BACKED_DAILY_OPS.md`, `scripts/smoke_file_backed_day.sh`, `tests/ops/test_file_backed_daily_smoke.py`. Files modified: `src/athena/cli.py`, `docs/MILESTONES.md`, `docs/PRODUCTION_READINESS_ROADMAP.md`, `IMPLEMENTATION_SUMMARY.md`, `README.md`. No ADR; R2+ still unauthorized.

---

## Phase 10 -- Live Dry-Run Operations & AI Playbook Learning (COMPLETE — owner closed 2026-07-23)

Phase outcome: M10.1–M10.4 owner-approved. FileProvider-backed dry-run ops, briefings, and propose-only playbook diagnostics delivered. Broker binding (DD-1) deferred. No order-placement code. Next: production-readiness tracks R1–R6 in `docs/PRODUCTION_READINESS_ROADMAP.md` (unauthorized until gated).

### M10.4 -- AI Playbook Diagnostics

| | |
|---|---|
| Completed | 2026-07-23 |
| Scope | Rules-based playbook diagnostics over run ledger + injectable decisions/journal; TuningProposal artifacts only; `athena diagnose`; never auto-applies config. |
| Tests | 870 passed / 0 failed (11 new diagnostics tests) |
| Status | **APPROVED** — Owner approved 2026-07-23; closes M10.4 and Phase 10 |
| Branch | develop |

Implemented propose-only diagnostics (no LLM; no R2 journal schema; no config mutation).
- `PlaybookDiagnosticsAnalyzer`: ops failure rate, insufficient-data share, gate concentration, adherence → threshold/weight proposals with `min_sample_size` gate (`blocked=True` when under-sampled).
- Paired scoring weight proposals keep sum-100 invariant in the proposed snapshot.
- `PlaybookDiagnosticsService` + `DiagnosticReportWriter` → `artifacts/diagnostics/diag-<date>.{json,txt}`.
- CLI: `athena diagnose [--as-of] [--dry-run]` (dry-run accepted; apply path does not exist).

Files created: `config/diagnostics.json`, `src/athena/diagnostics/{__init__.py,models.py,analyzer.py,writer.py,service.py}`, `tests/runtime/test_diagnostics.py`. Files modified: `src/athena/config/{models.py,loader.py,__init__.py}`, `src/athena/errors.py`, `src/athena/cli.py`, `docs/MILESTONES.md`, `IMPLEMENTATION_SUMMARY.md`. Public APIs: `DiagnosticReport`, `TuningProposal`, `PlaybookDiagnosticsService`, `load_diagnostics_config`, `athena diagnose`. No ADR; human approval required for any config change; R1–R6 still unauthorized.

### M10.3 -- Daily Briefing Notifications

| | |
|---|---|
| Completed | 2026-07-23 |
| Scope | Assemble immutable DailyBriefing from SQLite run ledger (+ optional injected decisions); dispatch via FileNotifier / optional WebhookNotifier; CLI `athena brief`. |
| Tests | 859 passed / 0 failed (8 new briefing tests) |
| Status | **APPROVED** — Owner approved 2026-07-23 |
| Branch | develop |

Implemented assemble→notify path (no decision-pipeline rebuild; no P8.9 alert center).
- `DailyBriefingBuilder`: runs for `as_of.date()` from ledger; missing runs → `BriefingError`; no decisions → `DEGRADED` with explicit reason; failed runs degrade.
- Notifiers: `FileNotifier` (JSON+txt), `WebhookNotifier` (`ATHENA_WEBHOOK_URL` from `.env`), `EmailNotifier` refuses loudly if enabled (SMTP deferred).
- `BriefingDispatcher` + config `notifications.json`; `--dry-run` forces file-only delivery.
- CLI: `athena brief [--as-of] [--dry-run]`.

Files created: `config/notifications.json`, `src/athena/notifications/{__init__.py,models.py,builder.py,notifiers.py,dispatch.py}`, `tests/runtime/test_daily_briefing.py`. Files modified: `src/athena/config/{models.py,loader.py,__init__.py}`, `src/athena/errors.py`, `src/athena/cli.py`, `docs/MILESTONES.md`, `IMPLEMENTATION_SUMMARY.md`. Public APIs: `DailyBriefing`, `BriefingDispatcher`, notifiers, `load_notifications_config`, `athena brief`. No ADR; secrets stay in `.env`; M10.4 AI deferred.

### M10.2 -- Scheduled Dry-Run Operations

| | |
|---|---|
| Completed | 2026-07-23 |
| Scope | Premarket + intraday refresh cadence; dry-run cycle = ingest → optional paper pipeline hook → SQLite run ledger; CLI `athena due` / `athena cycle`. |
| Tests | 851 passed / 0 failed (12 new dry-run/cadence tests) |
| Status | **APPROVED** — Owner approved 2026-07-23 |
| Branch | develop |

Implemented schedule cadence and dry-run cycle orchestration (no embedded cron; external launcher may call CLI).
- Extended `SchedulingConfig` / `scheduling.json` with `premarket.run_at` and `refresh.interval_minutes` (null → `base.refresh_interval_minutes`).
- Pure cadence helpers: `is_premarket_due`, `is_refresh_due`, `due_triggers` (injected `as_of` + last-run markers).
- `DryRunCycleOrchestrator.run_cycle(trigger, as_of=…)`: `LiveIngestionEngine` → optional `DryRunPipeline` → persist `RunRecord` (FAILED runs saved before re-raise).
- SQLite schema v2: append-only `runs` table; `save_run` / `get_run` / `list_runs` / `latest_run`; `initialize` upgrades version.
- CLI: `athena due [--as-of]`, `athena cycle --trigger premarket|refresh [--as-of]`.

Files created: `src/athena/scheduling/{cadence.py,dry_run.py}`, `tests/runtime/test_dry_run_schedule.py`. Files modified: `config/scheduling.json`, `src/athena/config/models.py`, `src/athena/scheduling/__init__.py`, `src/athena/data/store/{schema.py,repository.py,serialization.py}`, `src/athena/cli.py`, `docs/MILESTONES.md`, `IMPLEMENTATION_SUMMARY.md`. Public APIs: cadence helpers, `DryRunCycleOrchestrator`, `DryRunCycleResult`, run ledger methods, `athena due`/`cycle`. No ADR; no broker SDK; no order placement; M10.3 notifications / M10.4 AI deferred.

### M10.1 -- Live Data Ingestion

| | |
|---|---|
| Completed | 2026-07-23 |
| Scope | Callable live ingest cycle: MarketDataProvider quotes/candles → duplicate/freshness validation → SQLite persist; FileProvider only; `athena ingest` CLI. |
| Tests | 839 passed / 0 failed (9 new ingestion tests) |
| Status | **APPROVED** — Owner approved 2026-07-23 |
| Branch | develop |

Implemented `LiveIngestionEngine.run_cycle(as_of=…)` as a deterministic poll→validate→persist step (scheduler deferred to M10.2).
- Config: `config/ingestion.json` + `IngestionConfig` / `load_ingestion_config` (provider=`file` only until DD-1).
- Reuses `DatasetValidator` (OHLC/duplicates/freshness; gaps off by default for live lookback) and `QuarantineRegistry`; adds `validate_quotes` for quote price/freshness/dupes.
- Empty candle fetches skip (provider contract); failed validation quarantines and raises `DataStaleError` / `DataValidationError` with no writes for that cycle’s failed path.
- `skip_existing` filters already-persisted candles/quotes for idempotent re-runs.
- CLI: `athena ingest [--as-of ISO]` wires FileProvider + calendar + SQLite (`ATHENA_DB_PATH` override).

Files created: `config/ingestion.json`, `src/athena/data/ingestion/{__init__.py,engine.py,models.py}`, `tests/data_layer/test_ingestion.py`. Files modified: `src/athena/config/{models.py,loader.py,__init__.py}`, `src/athena/data/validation/{validators.py,__init__.py}`, `src/athena/cli.py`, `docs/MILESTONES.md`, `IMPLEMENTATION_SUMMARY.md`. Public APIs: `LiveIngestionEngine`, `IngestionResult`, `build_ingest_validator`, `validate_quotes`, `load_ingestion_config`, `athena ingest`. No ADR; frozen `MarketDataProvider` unchanged; no broker SDK; no order methods.

---

## Phase 9 -- Dashboard & Operations Console (COMPLETE — owner closed 2026-07-23)

Phase outcome: single-user workstation console delivered and approved (P9.1–P9.7), including console reliability hotfixes and Overview capital correctness. Architecture frozen; no order-placement code; Phase 10 authorized after Phase 9 close.

### P9.7 -- Live Monitoring & Admin

| | |
|---|---|
| Completed | 2026-07-23 |
| Scope | Replace Live Operations placeholder with SSE warning stream, stage telemetry Chart.js bars, and CONFIRM-gated SQLite backup/restore admin controls. |
| Tests | 830 passed / 0 failed (11 new ops + hosting update) |
| Status | **APPROVED** — closes P9.7 and Phase 9 (Owner approved) |
| Branch | develop |

Implemented Live Operations workstation APIs and UI on `#tab-operations`.
- Added `GET /api/v1/ops/stream` (SSE heartbeats + derived health/metrics/stage/database warnings).
- Added `GET /api/v1/ops/telemetry` aggregating latest pipeline stage statuses for charts.
- Added `GET/POST /api/v1/ops/backups` and `POST /api/v1/ops/backups/{id}/restore` reusing `create_backup` / `restore_backup`; restore requires exact token `CONFIRM`.
- Built Operations UI: EventSource warning feed, horizontal stage telemetry chart, backup list + create/restore admin panel.
- Clarified restore UX (CONFIRM unlocks buttons; explicit row click required; toast + last-restore feedback).
- Paths configurable via `ATHENA_DB_PATH` / `ATHENA_BACKUP_DIR` and `app.state.ops_*` for tests; missing live DB fails loudly (503).

Files created: `src/athena/api/v1/dtos/ops.py`, `src/athena/api/v1/services/ops_service.py`, `src/athena/api/v1/routers/ops.py`, `tests/api/v1/test_ops.py`. Files modified: `src/athena/api/v1/router.py`, `src/athena/api/dependencies.py`, `src/athena/api/exceptions.py`, `src/athena/api/errors.py`, `src/athena/api/v1/dtos/__init__.py`, `src/athena/api/static/{index.html,dashboard.js,dashboard.css}`, `tests/api/platform/test_dashboard_hosting.py`, `docs/MILESTONES.md`, `IMPLEMENTATION_SUMMARY.md`. Public APIs added: ops stream/telemetry/backups/restore. No ADR; frozen contracts preserved; Phase 9 closed before Phase 10 authorization.

---

### Hotfix -- Console modal leak & loader failure UX (2026-07-23)

| | |
|---|---|
| Completed | 2026-07-23 |
| Scope | Repair workstation console defects observed in live screenshots: inactive modals leaking into page flow, silent loader failures leaving permanent "Loading..." states, and a fake Live Operations loader ahead of P9.7. |
| Tests | 819 passed / 0 failed (hosting suite extended +1) |
| Status | **OWNER VERIFIED** — not a new milestone; hardening of P9.1–P9.6 console |
| Branch | develop |

Root cause: `.modal-overlay` previously used `display: flex` while inactive (opacity-only hide), so trace/backtest modal chrome rendered inside the document flow across every tab. Concurrently, auth/env startup gaps caused API failures; strategies/decisions loaders swallowed errors and never cleared placeholder text.
- Moved trace and backtest modals outside `#app`, marked `hidden` + `aria-hidden` at rest, and forced inactive overlays to `display: none !important`.
- Added `openModal` / `closeModal` / Escape-to-dismiss helpers; cache-busted static assets to `?v=9.6.2`.
- Hardened Market / Strategies / Decisions loaders to always replace Loading placeholders on empty, error, or missing context (with nested `final_context` fallback).
- Replaced Live Operations fake loader with an explicit P9.7 placeholder (milestone not started — no speculative ops UI).
- Extended `tests/api/platform/test_dashboard_hosting.py` to lock modal inertness and placeholder contracts.

Files modified: `src/athena/api/static/index.html`, `src/athena/api/static/dashboard.css`, `src/athena/api/static/dashboard.js`, `tests/api/platform/test_dashboard_hosting.py`, `IMPLEMENTATION_SUMMARY.md`.

---

### Correctness patch -- Overview exposure & day-change (2026-07-23)

| | |
|---|---|
| Completed | 2026-07-23 |
| Scope | Fix capital-screen correctness: sector donut was 100% fake cash because summary omitted `exposure_by_sector`; day-% was a hardcoded HTML placeholder. |
| Tests | 819 passed / 0 failed |
| Status | **OWNER VERIFIED** |
| Branch | develop |

- Extended `DashboardSummaryDTO` with `exposure_by_sector` and `day_change_pct`.
- `DashboardService` now maps portfolio sector exposure + cash into absolute ₹ slices and computes day-change from the two most recent NAV snapshots.
- Seeded prior-day + current NAV snapshots aligned to live portfolio value (₹1,25,050) so Overview chart and % are deterministic.
- Wired Overview UI for day-change (+/− classes) and sector tooltips; title-cased strategy profile names.
- Updated summary + analytics list tests; cache-bust `?v=9.6.3`.

Files modified: `src/athena/api/v1/dtos/dashboard.py`, `src/athena/api/v1/services/dashboard_service.py`, `src/athena/api/dependencies.py`, `src/athena/api/v1/providers/in_memory.py`, `src/athena/api/static/{index.html,dashboard.js}`, `tests/api/platform/test_dashboard_summary.py`, `tests/api/v1/test_reports_analytics_export.py`, `IMPLEMENTATION_SUMMARY.md`, `docs/MILESTONES.md`.

---

### P9.6 -- Decision Trace DAG Viewer

| | |
|---|---|
| Completed | 2026-07-23 |
| Scope | Implement backend REST trace endpoint, briefing document browser list, and interactive 7-node DAG flowchart rendering connection lines using SVG overlay layers. |
| Tests | 818 passed / 0 failed (3 new) |
| Status | **APPROVED** — closes P9.6 (Owner approved) |
| Branch | develop |

Implemented backend services and interactive visual workstation features to explore decision rationales.
- Created `GET /api/v1/decisions/{id}/trace` resolving execution logs and mapping variables to 7 sequential pipeline stages.
- Developed search-enabled Briefing Documents browser card listing past recommendation entries.
- Designed node flow diagram representing Universe Ingest, Indicators, Scoring, Confidence, Risk, Quality Gates, and Recommendation outputs.
- Programmed dynamic connector line drawing inside absolute SVG viewport, wired to window resize triggers.
- Wired click-to-open node parameter details card rendering composite scores, indicators thresholds, and gate checklists.

Files created: `tests/api/v1/test_decision_trace.py`. Files modified: `src/athena/api/v1/dtos/decisions.py`, `src/athena/api/v1/dtos/__init__.py`, `src/athena/api/v1/services/decisions_service.py`, `src/athena/api/v1/routers/decisions.py`, `src/athena/api/static/index.html`, `src/athena/api/static/dashboard.js`, `src/athena/api/static/dashboard.css`, `docs/MILESTONES.md`. Public APIs added: `GET /api/v1/decisions/{id}/trace`. 3 new integration tests validating trace node schemas and exception parameters. All quality checks pass; 818 total suite tests run successfully.

---

### P9.5 -- Strategy & Backtest Workspace

| | |
|---|---|
| Completed | 2026-07-23 |
| Scope | Implement backend APIs, seed mock runs, and build front-end workstation widgets under the Strategies & Scans tab (`#tab-strategies`) to display active strategy profiles and historical backtest runs. |
| Tests | 815 passed / 0 failed (6 new) |
| Status | **APPROVED** — closes P9.5 (Owner approved) |
| Branch | main |

Implemented backend services, mock seeding, and interactive workstation UI components for strategy configuration and backtest execution.
- Created `GET /api/v1/strategies/profiles` returning active strategy profiles and selection rules.
- Created `GET /api/v1/backtests/runs` and `GET /api/v1/backtests/runs/{run_id}` exposing backtest replays and performance metrics.
- Seeded a 10-step mock backtest session spanning all 5 reference strategies inside `in_memory.py`.
- Developed a two-column UI grid displaying Strategy Profiles Matrix and Backtest Replays.
- Integrated a Chart.js comparison bar chart showing completed vs failed steps for each run.
- Implemented a detailed modal drawer showing chronological timelines and horizontal strategy match performance bars.

Files created: `src/athena/api/v1/dtos/strategies.py`, `src/athena/api/v1/dtos/backtests.py`, `src/athena/api/v1/services/strategies_service.py`, `src/athena/api/v1/services/backtests_service.py`, `src/athena/api/v1/routers/strategies.py`, `src/athena/api/v1/routers/backtests.py`, `tests/api/v1/test_strategies_backtests.py`. Files modified: `src/athena/api/v1/dtos/__init__.py`, `src/athena/api/v1/providers/base.py`, `src/athena/api/v1/providers/in_memory.py`, `src/athena/api/dependencies.py`, `src/athena/api/v1/router.py`, `src/athena/api/exceptions.py`, `src/athena/api/errors.py`, `src/athena/api/static/index.html`, `src/athena/api/static/dashboard.js`, `src/athena/api/static/dashboard.css`, `docs/MILESTONES.md`. Public APIs added: `GET /api/v1/strategies/profiles`, `GET /api/v1/backtests/runs`, `GET /api/v1/backtests/runs/{id}`. 6 new integration tests validating payload formats, authentication guards, and details lookup. All quality checks pass; 815 total suite tests run successfully.

---

### P9.4 -- Market & Universe Dashboard

| | |
|---|---|
| Completed | 2026-07-23 |
| Scope | Build the Swing Trading Workstation's Market Intelligence and Universe Dashboard containing Volatility regime badges, interactive trading calendar session grid, and search-enabled Universe inclusion traces. |
| Tests | 809 passed / 0 failed (1 new) |
| Status | **APPROVED** — closes P9.4 (Owner approved) |
| Branch | main |

Implemented visual market and universe dashboard workstation panels under `src/athena/api/static/`.
- Created `GET /api/v1/dashboard/calendar` returning NSE segment holidays, expiries, special timings, and macro events.
- Extended dashboard service to resolve and load calendar configuration files dynamically.
- Seeded sample pipeline runs with volatility regime evaluations and eligibility traces in `in_memory.py`.
- Designed three-column grid workstation layout displaying Trend/Volatility/Gap badges, health gauge, interactive calendar cells with dots indicators, and search-enabled universe list.
- Implemented step-by-step eligibility trace inspector modals detailing rule checks outcomes (PASS/FAIL).

Files created: None. Files modified: `src/athena/api/v1/dtos/dashboard.py`, `src/athena/api/v1/services/dashboard_service.py`, `src/athena/api/v1/routers/dashboard.py`, `src/athena/api/v1/providers/in_memory.py`, `src/athena/api/static/index.html`, `src/athena/api/static/dashboard.js`, `src/athena/api/static/dashboard.css`, `tests/api/v1/test_core_apis.py`. Public APIs added: `GET /api/v1/dashboard/calendar`. 1 new integration test validating calendar structure. All quality checks pass; 809 total suite tests run successfully.

---

### P9.3 -- Portfolio & Capital Allocation Dashboard

| | |
|---|---|
| Completed | 2026-07-22 |
| Scope | Build visual dashboard components showing exposure breakdowns, asset balances, and portfolio charts including NAV area line chart, Sector Exposure donut chart, and open holdings table detail. |
| Tests | 818 passed / 0 failed (0 new) |
| Status | **APPROVED** — closes P9.3 (Owner approved) |
| Branch | main |

Implemented visual portfolio dashboard components under `src/athena/api/static/` utilizing Chart.js CDN hosting.
- Integrated canvas configurations for `#nav-chart` and `#sector-chart` inside `index.html`.
- Implemented `renderNavChart(snapshots)` and `renderSectorChart(exposure)` functions in `dashboard.js` with responsive configurations, tooltips, currency formatting, and fallback points.
- Wired charts rendering to load portfolio performance snapshots data asynchronously from `/api/v1/analytics/performance/snapshots`.
- Introduced environment-controlled single-user mode authentication bypass when `ATHENA_SINGLE_USER=true` is set.

Files created: None. Files modified: `src/athena/api/static/index.html`, `src/athena/api/static/dashboard.js`, `src/athena/api/security/dependencies.py`, `task.md`. Public APIs added: None. All quality checks pass; 818 total suite tests run successfully.

---

## Phase 8 -- Application Platform (completed)

### P8.5 -- API Platform Completion & Production Readiness

| | |
|---|---|
| Completed | 2026-07-22 |
| Scope | Finalize the API platform infrastructure and establish a production-grade API foundation with health, versioning, metadata, feature/capability discovery, standard headers, request context middleware, unified RFC 9457 error mappings, and OpenAPI contract completeness. |
| Tests | 806 passed / 0 failed (7 new) |
| Status | **APPROVED** — closes P8.5 (Owner approved) |
| Branch | main |

Finalized REST API platform infrastructure.
- Established a dedicated `platform` module defining extensible `BuildInfoProvider` and `MetadataProvider` protocols.
- Implemented `/health`, `/health/live`, and `/health/ready` check diagnostics.
- Implemented `/api/version` and `/api/info` consolidated startup metadata endpoints for desktop/UI clients.
- Introduced `PlatformMiddleware` combining request ID, correlation ID, logging, execution timing, standard headers injection, and unhandled exception-to-ProblemDetails mapping.
- Standardized error handling, migrating all mappings to use unified RFC 9457 `ProblemDetail` schemas.
- Audited all routes to confirm OpenAPI tags, operation IDs, summaries, descriptions, and pagination metadata schemas are 100% complete and consistent.

Files created: `src/athena/api/platform/health.py`, `src/athena/api/platform/version.py`, `src/athena/api/platform/metadata.py`, `src/athena/api/platform/info.py`, `src/athena/api/platform/headers.py`, `src/athena/api/platform/problem_details.py`, `src/athena/api/platform/middleware.py`, `src/athena/api/platform/providers/build_info_provider.py`, `src/athena/api/platform/providers/metadata_provider.py`, `tests/api/platform/test_platform.py`, `docs/API_PLATFORM_GUIDE.md`. Files modified: `src/athena/api/app.py`, `src/athena/api/errors.py`, `src/athena/api/dependencies.py`, `src/athena/api/v1/routers/health.py`, `src/athena/api/v1/routers/metrics.py`. Public APIs added: `GET /health`, `GET /health/live`, `GET /health/ready`, `GET /api/version`, `GET /api/meta`, `GET /api/features`, `GET /api/capabilities`, `GET /api/info`. 7 new integration tests validating process liveness/readiness, headers propagation, timing, unhandled panic mappings, contract schemas, and pagination consistency. All quality checks pass; 806 total suite tests run successfully.

---

### P8.4 -- Reports, Analytics & Export APIs

| | |
|---|---|
| Completed | 2026-07-22 |
| Scope | Expose Generic Reports, Portfolio Performance Analytics, and Presentation Format Export generation endpoints under versioned REST paths, backed by CQRS-aligned query and command providers. |
| Tests | 799 passed / 0 failed (14 new) |
| Status | **APPROVED** -- closes P8.4 (Principal Engineer review passed) |
| Branch | main |

Implemented reports, analytics, and exports API endpoints under versioned REST paths `/api/v1/`.
- Domain exceptions (`ReportNotFoundError`, `PerformanceSnapshotNotFoundError`, `ExportSnapshotNotFoundError`, `ExportArtifactNotFoundError`, `ExportGenerationError`) registered and mapped to HTTP Problem Details.
- Composed, nested DTOs (including `ArtifactMetadataDTO`, `ReportMetadataDTO`, `AnalyticsProvenanceDTO`, `SourceReferenceDTO`, `ExportOptionsDTO`, `ExportRequestDTO`, `ExportJobDTO`) decouple the transport interface from internal structures.
- Structured export requests and job status wrappers model export generation as a job abstraction, maintaining forward-compatibility for future asynchronous workers.
- CQRS-aligned provider separation decouples query interfaces from command mutation.
- Verified lease privilege and RBAC permission checks across all endpoints.

Files created: `src/athena/api/v1/dtos/reports.py`, `src/athena/api/v1/dtos/analytics.py`, `src/athena/api/v1/dtos/exports.py`, `src/athena/api/v1/services/reports_service.py`, `src/athena/api/v1/services/analytics_service.py`, `src/athena/api/v1/services/exports_service.py`, `src/athena/api/v1/routers/reports.py`, `src/athena/api/v1/routers/analytics.py`, `src/athena/api/v1/routers/exports.py`, `tests/api/v1/test_reports_analytics_export.py`. Files modified: `src/athena/api/v1/dtos/base.py`, `src/athena/api/v1/dtos/__init__.py`, `src/athena/api/exceptions.py`, `src/athena/api/errors.py`, `src/athena/api/v1/providers/base.py`, `src/athena/api/v1/providers/in_memory.py`, `src/athena/api/dependencies.py`, `src/athena/api/v1/services/__init__.py`, `src/athena/api/v1/routers/__init__.py`, `src/athena/api/v1/router.py`. Public APIs added: `GET /api/v1/reports`, `GET /api/v1/reports/{id}`, `GET /api/v1/analytics/performance/snapshots`, `GET /api/v1/analytics/performance/snapshots/{id}`, `GET /api/v1/exports/snapshots`, `GET /api/v1/exports/snapshots/{id}`, `GET /api/v1/exports/artifacts/{id}`, `POST /api/v1/exports`. 14 new integration tests covering listing summaries, detail specs, provenance tracking, dynamic export generation jobs, and header/permission guards. All 10 validation checklist items passed; 799 total suite tests pass clean.

---

### P8.3 -- Core Platform APIs

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Expose trading decisions, portfolios, execution run logs, scheduling history, and workspace snapshots under secure, authenticated, role-based controls. |
| Tests | 785 passed / 0 failed (14 new) |
| Status | **APPROVED** -- closes P8.3 (Principal Engineer review passed) |
| Branch | main |

Implemented core intelligence and operational API resources under versioned REST paths `/api/v1/`.
- Domain lookup exceptions mapped to RFC 9457 HTTP Problem Details via `AthenaExceptionMapper` (e.g. `DecisionNotFoundError`, `PortfolioUnavailableError`).
- Composed, generic DTO structures defined under `athena.api.v1.dtos.base` (including `CollectionResult`, `QuerySpecification`, `ResourceReference`).
- Decisions, Portfolios, Pipelines, Scheduler, and Workspace services map internal domain objects to clean public DTOs.
- Secured all routes with `RequirePermission(Permission.READ)` dependency.
- Collection list endpoints support query-based specification parsing for pagination, sorting, and filtering.
- Consolidated DTO optimization ensures workspace snapshots list returns lightweight metadata summaries while GET details returns full entries.

Files created: `tests/api/v1/test_core_apis.py`. Files modified: `src/athena/api/exceptions.py`, `src/athena/api/errors.py`, `src/athena/api/v1/dtos/__init__.py`, `src/athena/api/v1/routers/decisions.py`, `src/athena/api/v1/routers/portfolio.py`, `src/athena/api/v1/routers/pipelines.py`, `src/athena/api/v1/routers/scheduler.py`, `src/athena/api/v1/routers/workspace.py`, `src/athena/api/v1/services/decisions_service.py`. Public APIs added: `GET /api/v1/decisions`, `GET /api/v1/decisions/{id}`, `GET /api/v1/portfolio`, `GET /api/v1/pipelines/runs`, `GET /api/v1/pipelines/runs/{id}`, `GET /api/v1/scheduler/history`, `GET /api/v1/scheduler/history/{id}`, `GET /api/v1/workspace/snapshots`, `GET /api/v1/workspace/snapshots/{id}`. 14 new integration tests covering listing pagination, specs, filtering, details lookup, error status, and permission/RBAC bounds. All 10 validation checklist items passed; 785 total suite tests pass clean.

---

### P8.2 -- Authentication & RBAC

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Introduce production-grade authentication and authorization: Users, Roles, Permissions, JWT, API Keys, Sessions, RBAC, Password hashing, Permission middleware, Token refresh, Audit logging |
| Tests | 771 passed / 0 failed (16 new) |
| Status | **APPROVED** -- closes P8.2 (Principal Engineer review passed) |
| Branch | main |

Implemented the production authentication and authorization layer. `SecurityConfig` isolates cryptographic parameters (secret keys, algorithms, expiries, rounds) into `APISettings`. `AuthenticatedPrincipal` defines the immutable, runtime security context carrying pre-resolved user ID, role, and fine-grained permissions. `PasswordHasher` protocol abstraction uses `BcryptPasswordHasher` for password validation, shielding high-level components from raw password schemas. `TokenSigner` and `TokenClaimsFactory` divide signature verification from JWT claim generation. API Key persistence is split between `APIKeyMetadata` (hashes and active flags) and `APIKeySecret` (one-time returned key plain-text `key_id.raw_secret`). `SessionStore` protocol abstracts session status and token rotation tracking, using an `InMemorySessionStore` implementation that revokes session trees upon detecting refresh token reuse. `AuthenticationProvider` and `AuthorizationProvider` coordinate credential verification and permission validation. Security exceptions are mapped inside `AthenaExceptionMapper` to generate RFC 9457 Problem Details. FastAPI dependencies `get_current_user` and `RequirePermission` guard controller routes, integrating natively with OpenAPI schemas. `LoggingAuditSink` writes structured audit events to stdout log lines.

Files created: `src/athena/api/security/exceptions.py`, `src/athena/api/security/models.py`, `src/athena/api/security/hashing.py`, `src/athena/api/security/token.py`, `src/athena/api/security/repos.py`, `src/athena/api/security/providers.py`, `src/athena/api/security/dependencies.py`, `src/athena/api/security/audit.py`, `src/athena/api/security/__init__.py`, `tests/api/v1/test_security.py`. Files modified: `src/athena/api/config.py` (SecurityConfig), `src/athena/api/errors.py` (mappings), `src/athena/api/app.py` (app state initialization). Public APIs added: None (dependencies and exceptions only). 16 security integration tests covering hashing, claim parsing, token rotation, API key hashing checks, RBAC route bounds, and custom security exceptions. All 10 validation checklist items passed; 771 total suite tests pass clean.

---

### P8.1 -- Platform API Foundation

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Design and implement ATHENA's production REST API infrastructure: FastAPI app factory, ASGI/Lifespan lifecycle, API versioning (`/api/v1/`), unified response envelope `AthenaResponse[T]`, generic filtering (`FilterParams`), pagination/sorting params, `HealthProvider`/`MetricsProvider` protocols, `AthenaExceptionMapper` (RFC 9457 Problem Details) |
| Tests | 755 passed / 0 failed (24 new) |
| Status | **APPROVED** -- closes P8.1 (Principal Engineer review passed) |
| Branch | main |

Implemented the production FastAPI REST API platform foundation. `APISettings` separates TransportConfig (deployment) from AppMetadataConfig (application identity) with secure-by-default empty CORS origin list. `create_app()` uses a lifespan context manager (`@asynccontextmanager lifespan`) to manage startup and shutdown events cleanly. `AthenaResponse[T]` is the single, unified response envelope used across all endpoints, carrying optional pagination and links metadata. `PaginationMeta` and `PaginationParams` are future-ready, reserving cursor fields next to standard offset page parameters. `FilterParams` and `SortParams` establish consistent collection query interfaces. `AthenaExceptionMapper` functions as a central registry mapping domain errors to HTTP status codes and RFC 9457 `ProblemDetail` structures. Service components (`HealthService` and `MetricsService`) depend entirely on abstract `HealthProvider` and `MetricsProvider` protocols, with default implementations reading from system health checks and returning scaffold telemetry metrics. Middlewares inject unique `X-Request-ID` headers to all responses and format structured request logs. OpenAPI 3.1 is auto-generated with interactive documentation at `/api/docs`.

Files created: `src/athena/api/config.py`, `src/athena/api/errors.py`, `src/athena/api/middleware.py`, `src/athena/api/dependencies.py`, `src/athena/api/app.py`, `src/athena/api/v1/router.py`, `src/athena/api/v1/dtos/base.py`, `src/athena/api/v1/dtos/common.py`, `src/athena/api/v1/providers/base.py`, `src/athena/api/v1/providers/observability.py`, `src/athena/api/v1/routers/health.py`, `src/athena/api/v1/routers/metrics.py`, `src/athena/api/v1/services/health_service.py`, `src/athena/api/v1/services/metrics_service.py`, `tests/api/conftest.py`, `tests/api/v1/test_health.py`, `tests/api/v1/test_metrics.py`, `tests/api/v1/test_error_handling.py`. Files modified: `pyproject.toml` (dependencies). Public APIs added: `GET /api/v1/health`, `GET /api/v1/metrics`, `/api/docs`. 24 new integration tests covering endpoint payloads, headers, CORS behavior, validation errors, and custom exception mappings. All 10 validation checklist items passed; 755 total suite tests pass clean.

---

## Phase 7 -- Production Orchestration & Scheduling (complete)

### P7.5 -- Pipeline Scheduler Registration

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Introduce scheduling-domain bridge adapter: `ScheduleRunRequest`, `PipelineScheduleRun`, `PipelineScheduleHistory`, `SystemScheduleAdapter` |
| Tests | 731 passed / 0 failed (26 new) |
| Status | **APPROVED** -- closes Phase 7 (Principal Engineer review passed) |
| Branch | main |

Introduced ATHENA's scheduling-domain bridge. `ScheduleRunRequest` is a stable, versioned input contract bundling `ScheduledJob`, `decisions`, `current_prices`, and `as_of`; validation fires at construction, establishing the request-rejected lifecycle boundary before execution begins. `PipelineScheduleRun` is a thin, immutable scheduling envelope holding only the scheduling-domain metadata (`schedule_run_id`, `job_id`, `definition_id`, `duration_seconds`) backed by `SystemPipelineResult` as the authoritative execution record -- no fields duplicated. `PipelineScheduleHistory` is an immutable append-only history exposed as a read-only property; the adapter holds the current instance and replaces it via `record()` with no mutable state leakage. `SystemScheduleAdapter` coordinates the four-step lifecycle: validate-and-build context (via private `_ScheduleContextBuilder`), measure duration, delegate to `SystemPipelineRunner`, wrap result, record history. Failure recording policy is lifecycle-based: request-rejected failures produce no history record; execution-started failures (pipeline failure, contract failure, workspace failure) always produce a `PipelineScheduleRun` and are always recorded. The scheduling domain never touches `PipelineDefinition`, artifact keys, or stage topology.

Files created: `src/athena/orchestration/schedule_models.py`, `src/athena/orchestration/schedule_adapter.py`, `tests/runtime/test_pipeline_scheduler.py`. Files modified: `src/athena/orchestration/__init__.py` (exported four new APIs). Public APIs added: `ScheduleRunRequest`, `PipelineScheduleRun`, `PipelineScheduleHistory`, `SystemScheduleAdapter`. Private (not exported): `_ScheduleContextBuilder`. 26 new tests across four test classes covering request validation, thin-envelope design, append-only history semantics, adapter execution lifecycle, failure recording policy, and scheduler-pipeline isolation. No ADR required; no architecture drift; zero technical debt. All 10 validation checklist items passed; 731 total suite tests pass clean.

---

### P7.4 -- Pipeline Runner Integration

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Implement integrated runtime orchestration layer: `PipelineContract`, `validate_contract`, `PipelineCoordinator`, `WorkspaceAssembler`, `SystemPipelineRunner`, `SystemPipelineResult` |
| Tests | 705 passed / 0 failed (12 new) |
| Status | **APPROVED** — closes P7.4 (Principal Engineer review passed) |
| Branch | main |

Implemented ATHENA's integrated production runtime. `PipelineContract` declares symmetric input/output requirements per pipeline; `validate_contract()` is a pure validation function that raises `OrchestrationError` on missing required inputs. `PipelineCoordinator` executes an ordered sequence of `(PipelineDefinition, PipelineContract)` pairs generically — enforcing contracts between runs and threading functional context — with no knowledge of specific artifact keys. `WorkspaceAssembler` is a standalone post-processing adapter that extracts intelligence artifacts from the final `PipelineContext` and delegates construction to `UnifiedIntelligenceWorkspace`, fully isolating workspace assembly from the orchestration layer. `SystemPipelineRunner` is the high-level system entry point, composing coordinator and assembler with explicit four-boundary failure handling: execution failure → immediate termination; contract validation failure → raises `OrchestrationError`; intelligence failure → skips workspace; workspace failure → exception caught, pipelines preserved, `overall_status=FAILED`. `SystemPipelineResult` is an immutable generic container holding `pipeline_runs: tuple[PipelineResult, ...]` to scale beyond two pipelines.

Files created: `src/athena/orchestration/contract.py`, `src/athena/orchestration/coordinator.py`, `src/athena/orchestration/workspace_adapter.py`, `src/athena/orchestration/system_runner.py`, `tests/runtime/test_pipeline_runner_integration.py`. Files modified: `src/athena/orchestration/models.py` (added `SystemPipelineResult`), `src/athena/orchestration/__init__.py` (exported all P7.4 APIs). Public APIs added: `PipelineContract`, `validate_contract`, `EXECUTION_PIPELINE_CONTRACT`, `INTELLIGENCE_PIPELINE_CONTRACT`, `PipelineCoordinator`, `WorkspaceAssembler`, `SystemPipelineRunner`, `SystemPipelineResult`. 12 new tests covering: contract construction and validation, coordinator sequence execution, coordinator contract failure boundary, workspace assembler extraction, end-to-end system cycle success, execution failure early exit, workspace assembly failure handling, deterministic replayability, and `FrozenInstanceError` immutability. No ADR required; no architecture drift; zero technical debt. All 10 validation checklist items passed; 705 total suite tests pass clean.

---

### P7.3 — Intelligence Pipeline Registration

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Wire six presentation/intelligence stage adapters into a validated, declarative `PipelineDefinition`; model topology as four independent producer roots, Timeline as intermediate aggregator, and Export as terminal aggregator |
| Tests | 693 passed / 0 failed (21 new) |
| Status | **APPROVED** — closes P7.3 (Owner approved) |
| Branch | main |

Built ATHENA's second production pipeline. `create_intelligence_pipeline()` returns an immutable `PipelineDefinition` with six stages: four independent roots (`ReportingStage`, `ExplainabilityStage`, `DashboardStage`, `MonitoringStage`), one intermediate aggregator (`TimelineStage` depending on the four roots), and one terminal aggregator (`ExportStage` depending on all five upstream stages). `validate_intelligence_pipeline()` enforces the correct topological shape, stage count (6), and expected stage IDs. The explicit execution-artifact input contract is defined by `INTELLIGENCE_PIPELINE_REQUIRED_INPUTS` and `INTELLIGENCE_PIPELINE_OPTIONAL_INPUTS` to prevent implicit runtime assumptions. `IntelligenceArtifactKey` and `IntelligenceStageId` enums eliminate all raw string keys in context propagation. Each stage adapter wraps its engine internally with no concrete engine injection at builder level.

Files created: `src/athena/orchestration/pipelines/intelligence.py`, `src/athena/orchestration/stages/{reporting,explainability,dashboard,monitoring,timeline,export}.py`, `tests/runtime/test_intelligence_pipeline.py`. Files modified: `src/athena/orchestration/pipelines/keys.py`, `src/athena/orchestration/pipelines/__init__.py`, `src/athena/orchestration/stages/__init__.py`, `src/athena/orchestration/__init__.py`. Public APIs added: `IntelligenceArtifactKey`, `IntelligenceStageId`, `INTELLIGENCE_PIPELINE_REQUIRED_INPUTS`, `INTELLIGENCE_PIPELINE_OPTIONAL_INPUTS`, `create_intelligence_pipeline`, `validate_intelligence_pipeline`, and all six stage classes. 21 new tests: registration, topology validation, stage count, roots, validators, stage execution, failure isolation, and deterministic replayability. No ADR; no drift; no tech debt. Validation checklist 1–10 passed; all 693 suite tests pass.

---

### P7.2 — Execution Pipeline Registration

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Wire all eight execution-domain stage adapters into a validated, declarative `PipelineDefinition` using the P7.1 generic orchestration framework; typed artifact key model replaces all string-based context access |
| Tests | 672 passed / 0 failed (7 new) |
| Status | **APPROVED** — closes P7.2 (Principal Engineer review passed) |
| Branch | main |

Built ATHENA's first production pipeline. `create_execution_pipeline()` returns an immutable `PipelineDefinition` (not a live executor) with eight `PipelineStage` adapters wired in correct topological order: two independent root stages (`PortfolioSnapshotStage`, `DecisionsLoadStage`) followed by `AllocationStage → SizingStage → OrderPlanningStage → BrokerTranslationStage → OrderLifecycleStage → PortfolioAnalyticsStage`. Each stage adapter owns its own engine dependencies and writes a typed `ExecutionArtifactKey` value into the context; no concrete engines are injected at the builder level. `validate_pipeline_definition()` asserts stage count, dependency integrity, key-to-stage consistency, and dual-root topology. `ExecutionArtifactKey` and `ExecutionStageId` enums replace all string-based context access, satisfying the typed key model requirement from the architecture review. Pipeline topology is immutable in code; operational parameters (timeout, retries) remain configurable via `PipelineConfig`. The dual-root design preserves future parallel execution of the two root stages without any structural change.

Files created: `src/athena/orchestration/pipelines/{__init__,keys,execution}.py`, `src/athena/orchestration/stages/{__init__,portfolio_snapshot,decisions,allocation,sizing,order_planning,broker_translation,lifecycle,analytics}.py`, `tests/runtime/test_execution_pipeline.py`. Files modified: `src/athena/orchestration/__init__.py` (exported new APIs). Public APIs added: `ExecutionArtifactKey`, `ExecutionStageId`, `create_execution_pipeline`, `validate_pipeline_definition`, and all eight stage classes. 7 new tests: definition type, stage count, dual independent roots, validator passes, stage execution artifact, failure isolation, deterministic replayability. Fixed 4 E501 linter warnings in stage success-message strings. No ADR; no drift; no tech debt. Validation checklist 1–10 passed; all 672 suite tests pass.

---

### P7.1 — Generic Pipeline Infrastructure

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Domain-agnostic pipeline execution framework: stage-based orchestration, typed execution context, composable retry/fallback/timeout policies, deterministic structured execution record |
| Tests | 665 passed / 0 failed (10 new) |
| Status | **APPROVED** — closes P7.1 (Principal Engineer review passed) |
| Branch | main |

Built the Generic Pipeline Infrastructure (`src/athena/orchestration/`). `PipelineExecutor` performs topological sort of `PipelineStage` dependencies, gates downstream stages on upstream success (propagates `SKIPPED` through dependents of failed stages), evaluates configurable `RetryPolicy` (max attempts + delay), invokes an optional `fallback_handler` on exhaustion, enforces `timeout_seconds` per stage, and accumulates all outcomes into an immutable `PipelineResult`. All data types are `frozen=True, slots=True`. The framework is entirely domain-independent — zero imports from any ATHENA business module.

**Phase 6 engine bug fixes (identified during P7.1 full-suite self-validation):** Seventeen stale field-name references in Phase 6 presentation/analytics engines (dashboard, explainability, timeline, monitoring, reporting, analytics/portfolio) were corrected against the actual `PortfolioSnapshot` and `AllocationPlanSummary` contracts. NAV formula in `analytics/portfolio/engine.py` corrected from `total_cash + gross_exp` (double-counted) to `available_cash + reserved_cash + gross_exp`. Two test files corrected (`test_portfolio_analytics.py` — wrong kwarg names and monotonic timestamp; `test_workspace.py` — fixture omitted `schedule_execution`/`workflow` sentinels). No domain models, frozen contracts, or business logic were changed.

Files created: `src/athena/orchestration/{__init__,models,engine}.py`, `config/pipeline.json`, `tests/runtime/test_orchestration.py`. Files modified (bug fixes only): `src/athena/reporting/engine.py`, `src/athena/dashboard/engine.py`, `src/athena/explainability/engine.py`, `src/athena/timeline/engine.py`, `src/athena/monitoring/engine.py`, `src/athena/analytics/portfolio/engine.py`, `tests/runtime/test_portfolio_analytics.py`, `tests/runtime/test_workspace.py`. Public APIs added: `PipelineStage`, `PipelineContext`, `StageResult`, `PipelineResult`, `RetryPolicy`, `PipelineExecutor`. 10 new tests: single-stage execution, dependency ordering, skip propagation, retry with success, retry exhaustion + fallback, timeout enforcement, deterministic independent ordering, deterministic replay, immutable outputs, config validation. No ADR; no drift; no tech debt. Validation checklist 1–10 passed; all 665 suite tests pass.

---

## Phase 1 — Data Foundation (complete)

### M1.6 — Backup & Restore  (completes Phase 1)

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Deterministic backup + restore with integrity verification, schema-compat enforcement, recovery validation |
| Tests | 182 passed / 0 failed (11 new) |
| Status | **APPROVED** — closes Phase 1 (Principal Engineer review passed) |
| Branch | main |

Built the backup/restore layer. `create_backup` integrity-verifies the source, snapshots it via SQLite's online backup API written atomically (temp + `os.replace`, so a backup file is always complete), and writes a JSON metadata sidecar (schema version, per-table counts, provenance). `restore_backup` validates the backup first (integrity + schema-version compatibility — no silent repair, no automatic migration), replaces the target atomically, clears stale WAL sidecars, then re-verifies the restored repository (integrity, foreign keys, schema version, record counts vs metadata) and reports the outcome. Every failure mode raises `RepositoryError` with an actionable message and never leaves the target inconsistent. Repository-focused; no business/provider/intelligence logic.

Files created: `src/athena/data/store/backup.py`, `tests/data_layer/test_backup_restore.py`. Files modified: `src/athena/data/store/{__init__,repository}.py` (exports; repo `path`/`connection`/`record_counts` accessors). Public APIs added: `create_backup`, `restore_backup`, `BackupResult`, `RestoreResult`. 11 new tests: successful backup/restore, overwrite behavior, read-only destination, recovery of every entity, restored==original, deterministic repeated cycles, missing/corrupted backup, incompatible schema refusal (+ target untouched), unhealthy-source refusal.

**Codebase-wide quality pass (this milestone):** ran `ruff` for the first time (not previously available in the sandbox). Applied safe modernizations tree-wide — `typing.List/Dict/Tuple/Optional/Union` → builtin generics and `X | None` (verified against the 3.10 floor; all tests green), raw-string regex patterns in tests, and minor nits. Set ruff `target-version = py310` and `line-length = 120` (a deliberate project-standard width suited to this explainability-heavy code, avoiding low-value wrapping churn). `ruff check src tests` now passes clean. `mypy` could not run — v2.3.0 in the sandbox crashes with an INTERNAL ERROR on any input (tooling bug); strict typing remains configured for `domain`/`config` and should be verified on the owner's machine.

Validation checklist 1–10 passed; frozen contracts unchanged; no ADR; no drift; no tech debt.

---

## Phase 6 — Reporting, Dashboards & User Intelligence (in progress)

### P6.7 — Unified Intelligence Workspace

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Read-only unified intelligence composition workspace orchestrating query lookups, artifact filtering, and consolidated snapshots across all Phase 6 intelligence artifacts |
| Tests | 669 passed / 0 failed (12 new) |
| Status | **Awaiting owner approval** — Phase 6 completed; Phase 7 blocked until approved |
| Branch | main |

Built the Unified Intelligence Workspace (`src/athena/workspace/`), which answers one question: "How can all immutable ATHENA intelligence artifacts be accessed through a single, unified, read-only interface?" `UnifiedIntelligenceWorkspace` provides a consolidated view across 6 canonical workspace views (`REPORT`, `DASHBOARD`, `EXPLAINABILITY`, `TIMELINE`, `MONITORING`, `EXPORT`) into `WorkspaceSnapshot`s. It **aggregates and organizes information only**: it performs no state mutation, no user authentication, no REST APIs, no Web/Desktop/Mobile UI rendering, and no market analysis.

Workspace features: `assemble_workspace(reports=None, dashboard_snapshot=None, explanation_snapshot=None, timeline_snapshot=None, monitoring_snapshot=None, export_snapshot=None, *, as_of)` aggregates all Phase 6 intelligence artifacts into cataloged `WorkspaceEntry` records, provides deterministic filtering (`filter_by_type()`), identifier lookup (`find_by_id()`), and a high-level `WorkspaceSummary`. All outputs (`WorkspaceEntry`, `WorkspaceSummary`, `WorkspaceSnapshot`, `WorkspaceHistory`) are immutable and preserve full `WorkspaceReferences` back to originating platform artifacts (`report_id`, `dashboard_snapshot_id`, `explanation_snapshot_id`, `timeline_snapshot_id`, `monitoring_snapshot_id`, `export_snapshot_id`).

Files created: `src/athena/workspace/{__init__,models,engine}.py`, `config/workspace.json`, `tests/runtime/test_workspace.py`. Files modified: `src/athena/errors.py` (+`WorkspaceError`), `src/athena/config/{models,loader,__init__}.py` (+`WorkspaceConfig`, `load_workspace_config`, exports). No analytical engine, export engine, monitoring engine, timeline engine, explainability engine, dashboard engine, reporting framework, order lifecycle engine, broker abstraction layer, order planning engine, position sizing engine, capital allocation engine, portfolio engine, scheduling framework, scanner, watchlist manager, strategy framework, backtesting engine, reporting & analytics engine, workflow engine, or frozen-domain type touched. Public APIs added: `UnifiedIntelligenceWorkspace`, `WorkspaceEntry`, `WorkspaceSummary`, `WorkspaceSnapshot`, `WorkspaceHistory`, `WorkspaceReferences`, `WorkspaceConfig`, `load_workspace_config`. 12 new tests: workspace assembly across all 6 Phase 6 artifact types, filtering by artifact type, lookup by ID, deterministic replay (`to_dict` & `to_json` equality), immutable outputs (`FrozenInstanceError`), append-only history, config validation (production config loading), and an **end-to-end integration test** consuming all Phase 6 intelligence artifacts. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; all prior engines and operational components unchanged.

### P6.6 — Export & Presentation Layer

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Presentation format transformation (JSON, Markdown, Text, CSV) for immutable platform artifacts; pure presentation adapter |
| Tests | 657 passed / 0 failed (12 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Export & Presentation Layer (`src/athena/export/`), which answers one question: "How can immutable ATHENA artifacts be exported and presented in standardized formats without changing their meaning or contents?" `ExportPresentationEngine` transforms immutable platform artifacts into 4 canonical presentation formats (`ExportFormat`: `JSON`, `MARKDOWN`, `TEXT`, `CSV`). It **transforms representations only**: it performs no state mutation, no PDF rendering, no REST endpoints, no file upload services, and no market analysis.

Export features: `export_report()`, `export_dashboard()`, `export_explanation()`, `export_timeline()`, `export_monitoring()`, and `create_snapshot(exports, *, as_of)`. Standardized format rendering ensures deterministic payloads, content-type mapping (`application/json`, `text/markdown`, `text/plain`, `text/csv`), and standardized extension generation (`.json`, `.md`, `.txt`, `.csv`). All outputs (`ExportRequest`, `ExportArtifact`, `ExportSummary`, `ExportSnapshot`, `ExportHistory`) are immutable and preserve full `ExportReferences` back to originating platform artifacts (`report_id`, `dashboard_snapshot_id`, `explanation_snapshot_id`, `timeline_snapshot_id`, `monitoring_snapshot_id`).

Files created: `src/athena/export/{__init__,models,engine}.py`, `config/export.json`, `tests/runtime/test_export.py`. Files modified: `src/athena/errors.py` (+`ExportError`), `src/athena/config/{models,loader,__init__}.py` (+`ExportConfig`, `ExportFormat`, `load_export_config`, exports). No analytical engine, monitoring engine, timeline engine, explainability engine, dashboard engine, reporting framework, order lifecycle engine, broker abstraction layer, order planning engine, position sizing engine, capital allocation engine, portfolio engine, scheduling framework, scanner, watchlist manager, strategy framework, backtesting engine, reporting & analytics engine, workflow engine, or frozen-domain type touched. Public APIs added: `ExportPresentationEngine`, `ExportRequest`, `ExportArtifact`, `ExportSummary`, `ExportSnapshot`, `ExportHistory`, `ExportReferences`, `ExportFormat`, `ExportConfig`, `load_export_config`. 12 new tests: export generation across all 4 canonical formats, format-specific content-type verification, deterministic replay (`to_dict` & `to_json` equality), immutable outputs (`FrozenInstanceError`), append-only history, config validation (production config loading), and an **end-to-end integration test** consuming Reporting, Dashboard, Explainability, Timeline, and Monitoring artifacts across all 4 formats. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; all prior engines and operational components unchanged.

### P6.5 — Operational Monitoring

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Operational health snapshot generation and component monitoring across 10 platform domains; read-only health observation only |
| Tests | 645 passed / 0 failed (12 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Operational Monitoring Engine (`src/athena/monitoring/`), which answers one question: "What is the current operational health of ATHENA and are all platform components functioning correctly?" `OperationalMonitoringEngine` evaluates platform health across 10 canonical domains (`MonitoringDomain`: `SCHEDULER`, `WORKFLOW`, `PORTFOLIO`, `EXECUTION`, `ANALYTICS`, `REPORTING`, `DASHBOARD`, `EXPLAINABILITY`, `TIMELINE`, `OVERALL`). It **observes operational health only**: it performs no state mutation, no live polling, no alert delivery, no Prometheus/Grafana integration, and no market analysis.

Monitoring features: `evaluate_health(schedule_execution=None, workflow=None, portfolio_snapshot=None, execution_state=None, performance_snapshot=None, reports=None, dashboard_snapshot=None, explanation_snapshot=None, timeline_snapshot=None, *, as_of)` aggregates component status, detects missing/stale artifacts, and computes overall platform health (`HEALTHY`, `DEGRADED`, `CRITICAL`). All outputs (`MonitoringCheck`, `MonitoringSummary`, `MonitoringSnapshot`, `MonitoringHistory`) are immutable and preserve full `MonitoringReferences` back to originating platform artifacts across every layer.

Files created: `src/athena/monitoring/{__init__,models,engine}.py`, `config/monitoring.json`, `tests/runtime/test_monitoring.py`. Files modified: `src/athena/errors.py` (+`MonitoringError`), `src/athena/config/{models,loader,__init__}.py` (+`MonitoringConfig`, `MonitoringDomain`, `load_monitoring_config`, exports). No analytical engine, timeline engine, explainability engine, dashboard engine, reporting framework, order lifecycle engine, broker abstraction layer, order planning engine, position sizing engine, capital allocation engine, portfolio engine, scheduling framework, scanner, watchlist manager, strategy framework, backtesting engine, reporting & analytics engine, workflow engine, or frozen-domain type touched. Public APIs added: `OperationalMonitoringEngine`, `MonitoringCheck`, `MonitoringSummary`, `MonitoringSnapshot`, `MonitoringHistory`, `MonitoringReferences`, `MonitoringDomain`, `MonitoringConfig`, `load_monitoring_config`. 12 new tests: component health check aggregation across 10 domains, missing artifact detection, overall status calculation, deterministic replay (`to_dict` & `to_json` equality), immutable outputs (`FrozenInstanceError`), append-only history, config validation (production config loading), and an **end-to-end integration test** consuming artifacts across the complete execution pipeline together with Reporting, Dashboard, Explainability, and Timeline engines. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; all prior engines and operational components unchanged.

### P6.4 — Timeline & Audit Engine

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Chronological timeline reconstruction and audit stream generation across 11 platform domains; read-only reconstruction only |
| Tests | 633 passed / 0 failed (12 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Timeline & Audit Engine (`src/athena/timeline/`), which answers one question: "What happened across the complete ATHENA pipeline, in what order, and how can every platform event be reconstructed?" `TimelineAuditEngine` reconstructs chronological timelines across 11 canonical domains (`TimelineDomain`: `DECISION`, `PORTFOLIO`, `ALLOCATION`, `SIZING`, `ORDER_PLANNING`, `BROKER_TRANSLATION`, `LIFECYCLE`, `ANALYTICS`, `REPORTING`, `DASHBOARD`, `EXPLAINABILITY`). It **reconstructs immutable history only**: it performs no state mutation, no live streaming, no distributed tracing, and no market analysis.

Timeline features: `build_timeline(decisions=None, portfolio_snapshot=None, allocation_plan=None, sizing_plan=None, execution_plan=None, broker_plan=None, execution_state=None, performance_snapshot=None, reports=None, dashboard_snapshot=None, explanation_snapshot=None, *, as_of)` extracts, sorts, and sequence-numbers platform events into causally ordered `AuditEntry` records inside a `TimelineSnapshot`. All outputs (`TimelineEvent`, `AuditEntry`, `TimelineSummary`, `TimelineSnapshot`, `TimelineHistory`) are immutable and preserve full `TimelineReferences` back to all originating platform artifacts across every layer.

Files created: `src/athena/timeline/{__init__,models,engine}.py`, `config/timeline.json`, `tests/runtime/test_timeline.py`. Files modified: `src/athena/errors.py` (+`TimelineAuditError`), `src/athena/config/{models,loader,__init__}.py` (+`TimelineConfig`, `TimelineDomain`, `load_timeline_config`, exports). No analytical engine, explainability engine, dashboard engine, reporting framework, order lifecycle engine, broker abstraction layer, order planning engine, position sizing engine, capital allocation engine, portfolio engine, scheduling framework, scanner, watchlist manager, strategy framework, backtesting engine, reporting & analytics engine, workflow engine, or frozen-domain type touched. Public APIs added: `TimelineAuditEngine`, `TimelineEvent`, `AuditEntry`, `TimelineSummary`, `TimelineSnapshot`, `TimelineHistory`, `TimelineReferences`, `TimelineDomain`, `TimelineConfig`, `load_timeline_config`. 12 new tests: timeline building across 11 domains, strict 1-indexed sequence numbering, deterministic replay (`to_dict` & `to_json` equality), immutable outputs (`FrozenInstanceError`), append-only history, config validation (production config loading), and an **end-to-end integration test** consuming artifacts across the complete execution pipeline together with Reporting, Dashboard, and Explainability engines. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; all prior engines and operational components unchanged.

### P6.3 — Explainability Engine

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Deterministic human-readable explanation generator explaining why decisions, allocations, sizing, execution plans, lifecycle outcomes, and analytics were produced; rationale only |
| Tests | 621 passed / 0 failed (12 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Explainability Engine (`src/athena/explainability/`), which answers one question: "Why did ATHENA produce this decision, allocation, position size, execution plan, lifecycle outcome, or analytical result?" `ExplainabilityEngine` generates deterministic, human-readable explanations across 9 canonical domains (`ExplanationDomain`: `DECISION`, `PORTFOLIO`, `ALLOCATION`, `SIZING`, `ORDER_PLANNING`, `BROKER_TRANSLATION`, `LIFECYCLE`, `ANALYTICS`, `REPORTING`). It **explains existing platform outcomes only**: it performs no state mutation, no decision altering, no LLM generation, and no market analysis.

Explainability features: `explain_decision()`, `explain_portfolio()`, `explain_allocation()`, `explain_sizing()`, `explain_order_planning()`, `explain_broker_translation()`, `explain_lifecycle()`, `explain_analytics()`, `explain_reporting()`, and `create_snapshot(explanations, *, as_of)`. All outputs (`ExplanationSection`, `Explanation`, `ExplanationSnapshot`, `ExplanationHistory`) are immutable and preserve full `ExplanationReferences` back to `decision_id`, `portfolio_snapshot_id`, `allocation_plan_id`, `position_sizing_plan_id`, `execution_plan_id`, `broker_execution_plan_id`, `execution_state_id`, `performance_snapshot_id`, `report_id`, and `schedule_execution_id`.

Files created: `src/athena/explainability/{__init__,models,engine}.py`, `config/explainability.json`, `tests/runtime/test_explainability.py`. Files modified: `src/athena/errors.py` (+`ExplainabilityError`), `src/athena/config/{models,loader,__init__}.py` (+`ExplainabilityConfig`, `ExplanationDomain`, `load_explainability_config`, exports). No analytical engine, dashboard engine, reporting framework, order lifecycle engine, broker abstraction layer, order planning engine, position sizing engine, capital allocation engine, portfolio engine, scheduling framework, scanner, watchlist manager, strategy framework, backtesting engine, reporting & analytics engine, workflow engine, or frozen-domain type touched. Public APIs added: `ExplainabilityEngine`, `ExplanationSection`, `Explanation`, `ExplanationSnapshot`, `ExplanationHistory`, `ExplanationReferences`, `ExplanationDomain`, `ExplainabilityConfig`, `load_explainability_config`. 12 new tests: explanation generation across all 9 canonical domains, deterministic replay (`to_dict` & `to_json` equality), immutable outputs (`FrozenInstanceError`), append-only history, config validation (production config loading), and an **end-to-end integration test** consuming artifacts across the complete execution pipeline together with Reporting and Dashboard engines. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; all prior engines and operational components unchanged.

### P6.2 — Dashboard & Snapshot Engine

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Derived, read-only operational dashboard snapshots aggregating platform status, portfolio health, execution progress, and analytics; presentation layer only |
| Tests | 609 passed / 0 failed (12 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Dashboard & Snapshot Engine (`src/athena/dashboard/`), which answers one question: "Given the current immutable platform artifacts, what is the current operational view of ATHENA?" `DashboardEngine` aggregates platform status across 9 canonical sections (`Portfolio Overview`, `Capital Allocation Overview`, `Active Positions`, `Execution Status`, `Order Lifecycle Summary`, `Portfolio Performance`, `Risk & Exposure Summary`, `Reporting Status`, `Platform Health`) into `DashboardSnapshot`s. It **presents derived operational views only**: it performs no state mutation, no UI rendering, no live polling, and no market analysis.

Dashboard features: `create_snapshot(portfolio_snapshot=None, allocation_plan=None, execution_state=None, performance_snapshot=None, reports=None, *, as_of)` aggregates available platform artifacts into modular `DashboardSection`s and a high-level `DashboardSummary`. All outputs (`DashboardSection`, `DashboardSummary`, `DashboardSnapshot`, `DashboardHistory`) are immutable and preserve full `DashboardReferences` back to `portfolio_snapshot_id`, `performance_snapshot_id`, `execution_state_id`, `allocation_plan_id`, `report_id`, and `schedule_execution_id`.

Files created: `src/athena/dashboard/{__init__,models,engine}.py`, `config/dashboard.json`, `tests/runtime/test_dashboard.py`. Files modified: `src/athena/errors.py` (+`DashboardError`), `src/athena/config/{models,loader,__init__}.py` (+`DashboardConfig`, `load_dashboard_config`, exports). No analytical engine, reporting framework, order lifecycle engine, broker abstraction layer, order planning engine, position sizing engine, capital allocation engine, portfolio engine, scheduling framework, scanner, watchlist manager, strategy framework, backtesting engine, reporting & analytics engine, workflow engine, or frozen-domain type touched. Public APIs added: `DashboardEngine`, `DashboardSection`, `DashboardSummary`, `DashboardSnapshot`, `DashboardHistory`, `DashboardReferences`, `DashboardConfig`, `load_dashboard_config`. 12 new tests: dashboard snapshot creation with all sections, partial artifact handling, deterministic replay (`to_dict` & `to_json` equality), immutable outputs (`FrozenInstanceError`), append-only history, config validation (production config loading), and an **end-to-end integration test** consuming real artifacts from Phase 5 execution pipeline and Reporting Framework. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; all prior engines and operational components unchanged.

### P6.1 — Reporting Framework

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Generic operational reporting engine generating immutable, structured machine-readable and human-readable reports from platform artifacts; read-only |
| Tests | 597 passed / 0 failed (12 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Reporting Framework (`src/athena/reporting/`), which answers one question: "Given ATHENA's completed artifacts from Phases 1–5, how can we produce generic, immutable, human-readable and structured operational reports?" `ReportingEngine` consumes immutable platform artifacts (`PortfolioSnapshot`, `ExecutionState`, `AllocationPlan`, `PerformanceSnapshot`, audit events) to produce `GenericReport`s. It **presents and formats information only**: it performs no state mutation, no order execution, no analytical calculation, and no market analysis.

Supported report types: `ReportType` (`PORTFOLIO`, `EXECUTION`, `ALLOCATION`, `ANALYTICS`, `AUDIT`). Report generation operations: `generate_portfolio_report(portfolio_snapshot, *, as_of)`, `generate_execution_report(execution_state, *, as_of)`, `generate_allocation_report(allocation_plan, *, as_of)`, `generate_analytics_report(performance_snapshot, *, as_of)`, `generate_audit_report(run_id, events, *, as_of)`. All reports provide dual presentation views (`to_dict()` machine-readable view and `to_text()` human-readable summary view). All outputs (`GenericReport`, `ReportingReferences`, `ReportingHistory`) are immutable and preserve full `ReportingReferences` back to `portfolio_snapshot_id`, `execution_state_id`, `allocation_plan_id`, `performance_snapshot_id`, `audit_id`, and `schedule_execution_id`.

Files modified: `src/athena/reporting/{__init__,models,engine}.py` (added `ReportingEngine`, `GenericReport`, `ReportingReferences`, `ReportingHistory` while preserving M3.7 `DecisionReportingEngine` & `DecisionReport` intact), `config/reporting.json`, `tests/runtime/test_reporting_framework.py`. Files modified: `src/athena/errors.py` (+`ReportingError`), `src/athena/config/{models,loader,__init__}.py` (+`ReportingFrameworkConfig`, `ReportType`, `load_reporting_framework_config`, exports). No analytical engine, order lifecycle engine, broker abstraction layer, order planning engine, position sizing engine, capital allocation engine, portfolio engine, scheduling framework, scanner, watchlist manager, strategy framework, backtesting engine, reporting & analytics engine, workflow engine, or frozen-domain type touched. Public APIs added: `ReportingEngine`, `GenericReport`, `ReportingReferences`, `ReportingHistory`, `ReportType`, `ReportingFrameworkConfig`, `load_reporting_framework_config`. 12 new tests: portfolio report generation, execution report generation, allocation report generation, analytics report generation, audit report generation, machine/text rendering verification, deterministic replay (`to_dict` & `to_json` equality), immutable outputs (`FrozenInstanceError`), append-only history, config validation (production config loading), and an **end-to-end integration test** consuming real artifacts across all Phases 1–5. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; all prior engines and operational components unchanged.

---

## Phase 5 — Portfolio & Execution Platform (COMPLETED)

### P5.7 — Portfolio Analytics & Performance

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Computes portfolio returns, realized/unrealized P&L, exposures, win/loss stats, and drawdowns; performance calculation only |
| Tests | 585 passed / 0 failed (12 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Portfolio Analytics Engine (`src/athena/analytics/portfolio/`), which answers one question: "Given completed portfolio activity and execution history, how has the portfolio performed?" `PortfolioAnalyticsEngine` consumes `PortfolioSnapshot`s and `ExecutionState`s to compute comprehensive performance metrics (`PortfolioPerformance`, `TradePerformance`, `AnalyticsSummary`, `PerformanceSnapshot`). It **computes performance metrics and analytics only**: it performs no investment decision making, no capital allocation, no position sizing, no order planning, no broker communication, and no execution state modification.

Core performance metrics & analytics: Realized P&L, unrealized P&L, total P&L, total return %, portfolio valuation, peak portfolio value, drawdown, drawdown %, max drawdown %, gross exposure, net exposure, cash utilization %, trade-level win/loss classification, win rate %, average gain, average loss, win/loss ratio, and average holding period (days). Analytics operations: `analyze(portfolio_snapshot, execution_state=None, current_prices=None, *, as_of)` processes portfolio state deterministically. All outputs (`TradePerformance`, `PortfolioPerformance`, `AnalyticsSummary`, `PerformanceSnapshot`, `PortfolioAnalyticsHistory`) are immutable and preserve full `PortfolioAnalyticsReferences` back to `execution_state_id`, `broker_execution_plan_id`, `execution_plan_id`, `position_sizing_plan_id`, `allocation_plan_id`, `portfolio_snapshot_id`, `decision_id`, `strategy`, `watchlist`, and `schedule_execution_id`.

Files created: `src/athena/analytics/portfolio/{__init__,models,engine}.py`, `config/portfolio_analytics.json`, `tests/runtime/test_portfolio_analytics.py`. Files modified: `src/athena/errors.py` (+`PortfolioAnalyticsError`), `src/athena/config/{models,loader,__init__}.py` (+`PortfolioAnalyticsConfig`, `load_portfolio_analytics_config`, exports). No analytical engine, order lifecycle engine, broker abstraction layer, order planning engine, position sizing engine, capital allocation engine, portfolio engine, scheduling framework, scanner, watchlist manager, strategy framework, backtesting engine, reporting & analytics engine, workflow engine, or frozen-domain type touched. Public APIs added: `PortfolioAnalyticsEngine`, `TradePerformance`, `PortfolioPerformance`, `AnalyticsSummary`, `PerformanceSnapshot`, `PortfolioAnalyticsHistory`, `PortfolioAnalyticsReferences`, `PortfolioAnalyticsConfig`, `load_portfolio_analytics_config`. 12 new tests: unrealized P&L & valuation, win/loss accounting & realized P&L, drawdown calculation, deterministic replay (`to_dict` & `to_json` equality), immutable outputs (`FrozenInstanceError`), append-only history, config validation (negative initial capital rejection, production config loading), and an **end-to-end integration test** consuming real outputs from the entire Phase 5 pipeline (`PortfolioEngine` → `CapitalAllocationEngine` → `PositionSizingEngine` → `OrderPlanningEngine` → `BrokerManager` → `OrderLifecycleEngine` → `PortfolioAnalyticsEngine`). ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; all prior engines and operational components unchanged.

### P5.6 — Order Lifecycle Engine

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Tracks order lifecycle states, validates legal state transitions, and records execution history; execution state model only |
| Tests | 573 passed / 0 failed (12 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Order Lifecycle Engine (`src/athena/execution/`), which answers one question: "What is the current lifecycle state of every planned order from creation until completion or cancellation?" `OrderLifecycleEngine` consumes `BrokerExecutionPlan`s and tracks order state transitions (`OrderLifecycleState`: `CREATED`, `ACCEPTED`, `SUBMITTED`, `PARTIALLY_FILLED`, `FILLED`, `CANCELLED`, `REJECTED`, `EXPIRED`). It **tracks execution state transitions only**: it performs no live broker polling, no WebSockets/REST communication, no exchange connectivity, and no market analysis.

State machine & transition features: Enforces strict legal state transition graph (e.g. `CREATED` → `SUBMITTED` → `PARTIALLY_FILLED` → `FILLED`); illegal transitions (e.g. `CREATED` → `FILLED`, or transitioning out of terminal states `FILLED`/`CANCELLED`/`REJECTED`/`EXPIRED`) fail loudly with `LifecycleError`. Accumulates fill quantities and calculates weighted average fill price (`avg_fill_price`). Auto-promotes `PARTIALLY_FILLED` to `FILLED` when 100% of target quantity is filled. All outputs (`ExecutionEvent`, `OrderLifecycle`, `LifecycleSummary`, `ExecutionState`, `LifecycleHistory`) are immutable and preserve full `ExecutionReferences` back to `broker_execution_plan_id`, `execution_plan_id`, `position_sizing_plan_id`, `allocation_plan_id`, `portfolio_snapshot_id`, `decision_id`, `strategy`, `watchlist`, and `schedule_execution_id`.

Files created: `src/athena/execution/{__init__,models,engine}.py`, `config/execution.json`, `tests/runtime/test_execution.py`. Files modified: `src/athena/errors.py` (+`LifecycleError`), `src/athena/config/{models,loader,__init__}.py` (+`ExecutionConfig`, `OrderLifecycleState`, `load_execution_config`, exports). No analytical engine, broker abstraction layer, order planning engine, position sizing engine, capital allocation engine, portfolio engine, scheduling framework, scanner, watchlist manager, strategy framework, backtesting engine, reporting & analytics engine, workflow engine, or frozen-domain type touched. Public APIs added: `OrderLifecycleEngine`, `OrderLifecycle`, `ExecutionEvent`, `ExecutionState`, `LifecycleSummary`, `LifecycleHistory`, `ExecutionReferences`, `OrderLifecycleState`, `ExecutionConfig`, `load_execution_config`. 12 new tests: legal state transitions, illegal transition rejection, terminal state protection, partial fills & weighted average price, cancellation, deterministic replay (`to_dict` & `to_json` equality), immutable outputs (`FrozenInstanceError`), append-only history, config validation (production config loading), and an **end-to-end integration test** consuming a real `BrokerExecutionPlan` from `BrokerManager`. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; all prior engines and operational components unchanged.

### P5.5 — Broker Abstraction Layer

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Canonical broker contracts, capability validation, and translation from broker-neutral execution plans into broker requests; contract definition only |
| Tests | 561 passed / 0 failed (12 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Broker Abstraction Layer (`src/athena/brokers/`), which answers one question: "How can ATHENA communicate with different brokers through a single canonical interface?" `BrokerManager` registers broker contract definitions (`BrokerDefinition`, `BrokerCapabilities`) and translates broker-neutral `ExecutionPlan`s into canonical `BrokerExecutionPlan`s containing `BrokerRequest`s. It **defines contracts and validates capabilities only**: it performs no network communication, no OAuth flows, no REST/WebSocket clients, and no live order submission.

Capability validation & contract features: `BrokerCapabilities` enforces supported order types (`OrderType`), fractional trading support (`supports_fractional`), shorting support (`supports_shorting`), and supported time-in-force policies (`TimeInForce`: `DAY`, `IOC`, `FOK`, `GTC`). Translation operations: `translate_plan(execution_plan, broker_id=None, *, as_of, time_in_force=None)` validates broker availability and capabilities, mapping planned orders into canonical `BrokerRequest`s (`ACCEPTED`, `REJECTED_UNSUPPORTED_ORDER_TYPE`, `REJECTED_UNSUPPORTED_FRACTIONAL`, `SKIPPED_HOLD`); `create_mock_response` generates abstract `BrokerResponse` artifacts for contract testing. All outputs (`BrokerDefinition`, `BrokerCapabilities`, `BrokerRequest`, `BrokerResponse`, `BrokerExecutionPlan`, `BrokerSummary`, `BrokerHistory`) are immutable and preserve full `BrokerReferences` back to `execution_plan_id`, `position_sizing_plan_id`, `allocation_plan_id`, `portfolio_snapshot_id`, `decision_id`, `strategy`, `watchlist`, and `schedule_execution_id`.

Files created: `src/athena/brokers/{__init__,models,engine}.py`, `config/brokers.json`, `tests/runtime/test_brokers.py`. Files modified: `src/athena/errors.py` (+`BrokerError`), `src/athena/config/{models,loader,__init__}.py` (+`BrokerConfig`, `TimeInForce`, `load_broker_config`, exports). No analytical engine, order planning engine, position sizing engine, capital allocation engine, portfolio engine, scheduling framework, scanner, watchlist manager, strategy framework, backtesting engine, reporting & analytics engine, workflow engine, or frozen-domain type touched. Public APIs added: `BrokerManager`, `BrokerDefinition`, `BrokerCapabilities`, `BrokerRequest`, `BrokerResponse`, `BrokerExecutionPlan`, `BrokerSummary`, `BrokerHistory`, `BrokerReferences`, `TimeInForce`, `BrokerConfig`, `load_broker_config`. 12 new tests: canonical translation, unsupported order type rejection, unsupported fractional quantity rejection, unsupported time-in-force error, mock response creation, unregistered & disabled broker handling, deterministic replay (`to_dict` & `to_json` equality), immutable outputs (`FrozenInstanceError`), append-only history, config validation (production config loading), and an **end-to-end integration test** consuming a real `ExecutionPlan` from `OrderPlanningEngine`. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; all prior engines and operational components unchanged.

### P5.4 — Order Planning Engine

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Transforms position sizes into broker-neutral execution instructions and batches; execution plan generation only |
| Tests | 549 passed / 0 failed (12 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Order Planning Engine (`src/athena/orders/`), which answers one question: "Given approved position sizes, what broker-neutral execution instructions should ATHENA prepare?" `OrderPlanningEngine` converts `PositionSizingPlan` outputs into broker-neutral `ExecutionPlan`s composed of `PlannedOrder`s grouped into `ExecutionBatch`es. It **prepares execution instructions only**: it performs no broker communication, no live order placement, no order fill tracking, and no market analysis.

Supported order actions & instruction types: `OrderAction` (`BUY`, `SELL`, `HOLD`) and `OrderType` (`MARKET`, `LIMIT`, `STOP`, `STOP_LIMIT`). Planning operations: `plan_execution(sizing_plan, *, as_of, decisions=None, order_type=None)` processes all position sizes in deterministic sorted order; `create_order(instrument_id, action, quantity, *, as_of, order_type=None, limit_price=None, stop_price=None)` creates a single explicit instruction. Batching policy (`batch_by_action`, `max_orders_per_batch`) groups planned orders into deterministic action batches (e.g. `BUY` batch, `SELL` batch) and chunks larger sets. Zero-quantity or `ZERO_ALLOCATION` items automatically generate `OrderAction.HOLD` instructions. All outputs (`PlannedOrder`, `OrderInstruction`, `ExecutionBatch`, `ExecutionPlan`, `OrderPlanningSummary`, `OrderPlanningHistory`) are immutable and preserve full `OrderReferences` back to `position_sizing_plan_id`, `allocation_plan_id`, `portfolio_snapshot_id`, `decision_id`, `strategy`, `watchlist`, and `schedule_execution_id`.

Files created: `src/athena/orders/{__init__,models,engine}.py`, `config/orders.json`, `tests/runtime/test_orders.py`. Files modified: `src/athena/errors.py` (+`OrderPlanningError`), `src/athena/config/{models,loader,__init__}.py` (+`OrderPlanningConfig`, `OrderAction`, `OrderType`, `load_order_planning_config`, exports). No analytical engine, position sizing engine, capital allocation engine, portfolio engine, scheduling framework, scanner, watchlist manager, strategy framework, backtesting engine, reporting & analytics engine, workflow engine, or frozen-domain type touched. Public APIs added: `OrderPlanningEngine`, `PlannedOrder`, `OrderInstruction`, `ExecutionBatch`, `ExecutionPlan`, `OrderPlanningSummary`, `OrderPlanningHistory`, `OrderReferences`, `OrderAction`, `OrderType`, `OrderPlanningConfig`, `load_order_planning_config`. 12 new tests: BUY planning, SELL planning, HOLD handling, MARKET & LIMIT order types, action batching & chunking, single order creation, deterministic replay (`to_dict` & `to_json` equality), immutable outputs (`FrozenInstanceError`), append-only history, config validation (positive batch size enforcement, production config loading), and an **end-to-end integration test** consuming a real `PositionSizingPlan` from `PositionSizingEngine`. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; all prior engines and operational components unchanged.

### P5.3 — Position Sizing Engine

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Converts approved capital allocations into executable share/unit quantities with rounding & precision policy; quantity calculation only |
| Tests | 537 passed / 0 failed (13 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Position Sizing Engine (`src/athena/sizing/`), which answers one question: "Given an approved capital allocation, how many units of the instrument should ATHENA purchase or sell?" `PositionSizingEngine` converts allocated capital amounts from an `AllocationPlan` into executable unit quantities based on instrument prices. It **calculates unit quantities only**: it performs no market analysis, no capital allocation policy decisions, no risk limit checks, and no order placement.

Supported sizing models & rounding policies: `WHOLE_SHARE` (integer share quantities via `int(raw_qty)`) and `FRACTIONAL` (decimal unit quantities up to configured `decimal_precision`, default 4 decimal places), combined with `ROUND_DOWN` (floor / conservative sizing ensuring cost <= allocation) or `ROUND_UP` (ceiling sizing). Sizing operations: `size_plan(allocation_plan, prices, *, as_of, model=None, rounding=None)` processes all allocations in deterministic sorted order; `size_amount(allocated_amount, unit_price, instrument_id, *, as_of)` calculates single-opportunity quantity. Zero-allocation items get `status="ZERO_ALLOCATION"`, `quantity=0`; missing or non-positive price items get `status="REJECTED_ZERO_PRICE"`, `quantity=0`. All outputs (`PositionSize`, `PositionSizingPlan`, `PositionSizingSummary`, `PositionSizingHistory`) are immutable and preserve full `SizingReferences` back to `allocation_plan_id`, `portfolio_snapshot_id`, `decision_id`, `strategy`, `watchlist`, and `schedule_execution_id`.

Files created: `src/athena/sizing/{__init__,models,engine}.py`, `config/sizing.json`, `tests/runtime/test_sizing.py`. Files modified: `src/athena/errors.py` (+`SizingError`), `src/athena/config/{models,loader,__init__}.py` (+`SizingConfig`, `SizingModel`, `RoundingMode`, `load_sizing_config`, exports). No analytical engine, capital allocation engine, portfolio engine, scheduling framework, scanner, watchlist manager, strategy framework, backtesting engine, reporting & analytics engine, workflow engine, or frozen-domain type touched. Public APIs added: `PositionSizingEngine`, `PositionSize`, `PositionSizingDecision`, `PositionSizingPlan`, `PositionSizingSummary`, `PositionSizingHistory`, `SizingReferences`, `SizingModel`, `RoundingMode`, `SizingConfig`, `load_sizing_config`. 13 new tests: whole-share sizing with round down & round up, fractional unit sizing with precision, zero-allocation handling, missing price handling, single-amount sizing, deterministic replay (`to_dict` & `to_json` equality), immutable outputs (`FrozenInstanceError`), append-only history, config validation (negative precision rejection, production config loading), and an **end-to-end integration test** consuming a real `AllocationPlan` from `CapitalAllocationEngine`. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; all prior engines and operational components unchanged.

### P5.2 — Capital Allocation Engine

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Policy-driven capital allocation per approved opportunity; enforces reserve floors and allocation models without position sizing or order execution |
| Tests | 524 passed / 0 failed (12 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Capital Allocation Engine (`src/athena/allocation/`), which answers one question: "How much capital should be reserved for each approved investment opportunity?" `CapitalAllocationEngine` evaluates available portfolio capital from a `PortfolioSnapshot` and allocates capital to candidate opportunities according to policy. It **determines capital allocation policy only**: it performs no market analysis, no position sizing (shares calculation), no risk limit checks, and no order execution.

Supported allocation models: `FIXED_AMOUNT` (configured fixed INR amount per opportunity), `FIXED_PERCENTAGE` (configured percentage of total portfolio cash), and `EQUAL_WEIGHT` (equal division of the allocatable pool among active candidates up to `max_opportunities`). Minimum cash reserve floor (`min_cash_reserve_pct`, default 20%) is strictly enforced before any allocation occurs (`allocatable_pool = max(0, available_cash - min_reserve_floor)`). Candidate opportunities (filtered for `TRADE` / `INCREASE_POSITION` decision types) are processed in deterministic sorted order. If remaining allocatable cash is less than target, a `status="PARTIAL"` allocation is issued; if pool is exhausted, `status="REJECTED_INSUFFICIENT_CASH"` or `REJECTED_RESERVE_FLOOR` is returned. Opportunities beyond `max_opportunities` are rejected as `REJECTED_MAX_OPPORTUNITIES`. `allocate_amount` provides explicit single-opportunity allocation. All outputs (`CapitalAllocation`, `AllocationPlan`, `AllocationSummary`, `AllocationHistory`) are immutable and preserve full `AllocationReferences` back to `portfolio_snapshot_id`, `decision_id`, `strategy`, `watchlist`, and `schedule_execution_id`.

Files created: `src/athena/allocation/{__init__,models,engine}.py`, `config/allocation.json`, `tests/runtime/test_allocation.py`. Files modified: `src/athena/errors.py` (+`AllocationError`), `src/athena/config/{models,loader,__init__}.py` (+`AllocationConfig`, `AllocationModel`, `load_allocation_config`, exports). No analytical engine, portfolio engine, scheduling framework, scanner, watchlist manager, strategy framework, backtesting engine, reporting & analytics engine, workflow engine, or frozen-domain type touched. Public APIs added: `CapitalAllocationEngine`, `CapitalAllocation`, `AllocationDecision`, `AllocationPlan`, `AllocationSummary`, `AllocationHistory`, `AllocationReferences`, `AllocationModel`, `AllocationConfig`, `load_allocation_config`. 12 new tests: fixed percentage allocation, fixed amount allocation, equal weight allocation, cash reserve threshold enforcement, max opportunities limit, partial & rejected statuses, deterministic replay (`to_dict` & `to_json` equality), immutable outputs (`FrozenInstanceError`), append-only history, config validation (negative values rejection, production config loading), and an **end-to-end integration test** consuming a real `PortfolioSnapshot` from `PortfolioEngine`. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; all prior engines and operational components unchanged.

### P5.1 — Portfolio Engine

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Deterministic portfolio state management, holdings, cash allocation, reserved capital, closed positions, and append-only history; state tracking only |
| Tests | 512 passed / 0 failed (18 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Portfolio Engine (`src/athena/portfolio/`), which answers one question: "Given ATHENA's completed investment decisions, what should the portfolio currently own?" `PortfolioEngine` manages portfolio state, active holdings, available cash, reserved capital, realized/closed positions, and append-only history. It **records state only**: it performs no market analysis, no position sizing calculations, no risk limit checks, and no order execution; it consumes completed `Decision` artifacts produced by the operational pipeline and maintains deterministic portfolio ledger state.

State operations: `open_position` (creates holding, allocates cash), `increase_position` (recomputes quantity & average price), `reduce_position` (reduces holding quantity, releases cost & records proceeds), `close_position` (removes holding, records immutable `ClosedPosition`, releases cash), `hold_position` (updates last-seen timestamp), `reserve_capital` / `release_capital` (allocates/frees reserved cash), and `apply_decision` (convenience mapper dispatching `open`, `increase`, `reduce`, `close`, or `hold` based on `DecisionType` and existing holdings). All operations return immutable `PortfolioSnapshot` objects referencing originating `decision_id`, `strategy`, `watchlist`, and `schedule_execution_id`. `PortfolioHistory` is **append-only** (`record()` returns a new history). Cash accounting enforces strict invariants (`total_cash == available + allocated + reserved`). Backdated operations, duplicate holdings on open, over-reduction, and cash deficits fail loudly with `PortfolioError`.

Files created: `src/athena/portfolio/{__init__,models,engine}.py`, `config/portfolio.json`, `tests/runtime/test_portfolio.py`. Files modified: `src/athena/errors.py` (+`PortfolioError`), `src/athena/config/{models,loader,__init__}.py` (+`PortfolioConfig`, `load_portfolio_config`, exports). No analytical engine, scheduling framework, scanner, watchlist manager, strategy framework, backtesting engine, reporting & analytics engine, workflow engine, or frozen-domain type touched. Public APIs added: `PortfolioEngine`, `Portfolio`, `PortfolioSnapshot`, `Holding`, `ClosedPosition`, `CashBalance`, `ReservedCapital`, `PortfolioReferences`, `PortfolioSummary`, `PortfolioHistory`, `PortfolioConfig`, `load_portfolio_config`. 18 new tests: open/increase/reduce/close/hold operations, capital reservation & release, `apply_decision` with TRADE & FULL_EXIT decisions, duplicate holding protection, insufficient cash handling, backdated timestamp rejection, deterministic replay (`to_dict` and `to_json` equality), immutable snapshots (`FrozenInstanceError`), append-only history, config validation (negative cash rejection, production config loading), and an **end-to-end integration test** consuming the completed operational pipeline via `SchedulingFramework`. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; all prior engines and operational components unchanged.

---

## Phase 4 — Orchestration & Operational Intelligence (APPROVED)

### M4.7 — Scheduling Framework (completes Phase 4)

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Deterministic execution coordination over the completed pipeline; schedules and records when ATHENA runs without changing how ATHENA analyzes markets |
| Tests | 494 passed / 0 failed (21 new) |
| Status | **APPROVED** — Principal Engineer review passed (completes Phase 4) |
| Branch | main |

Built the Scheduling Framework (`src/athena/scheduling/`), which answers one question: "When should ATHENA execute its existing operational pipeline?" `SchedulingFramework` coordinates the execution of existing operational components — the M4.1 `WorkflowEngine`, M4.2 `DailyMarketScanner`, M4.3 `WatchlistManager`, M4.4 `StrategyFramework`, M4.5 `BacktestingEngine`, and M4.6 `ReportingAnalyticsEngine`. It **coordinates execution only**: it invokes no analytical engine directly, evaluates no strategy rules, derives no market intelligence, and modifies no completed decision.

Two execution paths: `execute(definition, *, as_of, pipeline_builder, universe, previous_watchlist=None)` runs the full daily pipeline (scanner → watchlist → strategy → analytics), returning an immutable `ScheduleExecution` referencing every upstream artifact (`scan_id`, `watchlist_snapshot_id`, `strategy_execution_id`, `analytics_report_id`); `execute_replay(definition, *, as_of, replay_points)` runs the replay pipeline (backtester → analytics), returning a `ScheduleExecution` referencing `backtest_run_id` and `analytics_report_id`. Five deterministic scheduling modes supported: `MANUAL`, `DAILY`, `WEEKLY`, `REPLAY`, `ONE_TIME`. Scheduling policies are configuration-driven (`config/scheduling.json`, `record_history` toggle). `ScheduleHistory` is **append-only** (`record()` returns a new history). **Failure isolation**: any pipeline or replay exception is caught, recorded as `ExecutionStatus.FAILED` with a diagnostic note, and never crashes the framework. Determinism: with `as_of` injected and no clock read for business decisions (monotonic clock used for duration measurement only), identical inputs produce identical execution records (verified). Disabled definitions are rejected loudly before execution.

Files created: `src/athena/scheduling/{__init__,models,engine}.py`, `config/scheduling.json`, `tests/runtime/test_scheduling.py`. Files modified: `src/athena/config/{models,loader,__init__}.py` (add `SchedulingConfig`, `load_scheduling_config`, exports). No analytical engine, scanner, watchlist manager, strategy framework, backtesting engine, reporting & analytics engine, workflow engine, or frozen-domain type touched. Public APIs added: `SchedulingFramework`, `ScheduleDefinition`, `ScheduledJob`, `ScheduleExecution`, `ExecutionReferences`, `ScheduleHistory`, `ScheduleSummary`, `ScheduleMode`, `SchedulingConfig`, `load_scheduling_config`. 21 new tests: full pipeline manual execution (all artifact references preserved), recurring schedules (daily/weekly/one-time modes), replay schedule execution (backtest + analytics references, execute() rejection of REPLAY mode), chronological execution ordering in history, deterministic rerun (`to_dict` equality), immutable outputs (`FrozenInstanceError` on execution and history), history filtering by definition and mode, summary generation, record_history disabled toggle, disabled definition rejection, failure isolation (BrokenScanner recorded as FAILED), config validation (unknown-key rejection, production config loads, missing fails loudly), and a **real end-to-end scheduled execution** through the full M4.1→M4.6 operational pipeline across three instruments. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; all prior engines and operational components unchanged.

### M4.6 — Reporting & Analytics

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Deterministic operational summaries and analytical statistics aggregated from completed artifacts; presentation + aggregation only |
| Tests | 473 passed / 0 failed (14 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Reporting & Analytics layer (`src/athena/analytics/`), which answers operational questions — "What happened today?", "How many instruments matched each strategy?", "How did decisions distribute across the universe?", "What activity occurred during replay?" — purely by aggregating completed artifacts from the M4.2 scanner, M4.3 watchlist manager, M4.4 strategy framework, and M4.5 backtester. `ReportingAnalyticsEngine` is **presentation + aggregation only**: it invokes no analytical engine, derives no new market intelligence, and modifies no completed decision. Every metric is a count or roll-up of an existing immutable artifact, and every report preserves references back to its sources.

Two entry points: `daily_report(scan_report, *, as_of, watchlist=None, strategy_execution=None)` produces a `kind="daily"` `AnalyticsReport` embedding `DailyAnalytics` (decision distribution taken from the scan's own summary; scan success/fail/skip counts; confidence and risk **level distributions** aggregated from completed decision reports; optional `WatchlistAnalytics` and `StrategyAnalytics`); `backtest_report(run, *, as_of)` produces a `kind="replay"` report embedding `BacktestAnalytics` (step counts, replay coverage, decision distribution summed across every replayed scan, and per-strategy match/instrument roll-ups from the run's performance). Confidence/risk distributions honour config: `confidence_levels`/`risk_levels` fix display order and `include_unknown` toggles the UNKNOWN bucket. Determinism: all inputs are immutable, no clock is read (`as_of` injected), distributions are built in fixed config-driven order, and `to_json()` emits sorted-key output — identical inputs yield an identical report (verified). Empty inputs produce empty distributions, not errors.

Files created: `src/athena/analytics/{__init__,models,engine}.py`, `config/analytics.json`, `tests/runtime/test_analytics.py`. Files modified: `src/athena/config/{models,loader,__init__}.py` (add `AnalyticsConfig`, `load_analytics_config`, exports). No analytical engine, scanner, watchlist manager, strategy framework, backtesting engine, workflow engine, or frozen-domain type touched. Public APIs added: `ReportingAnalyticsEngine`, `AnalyticsReport`, `DailyAnalytics`, `WatchlistAnalytics`, `StrategyAnalytics`, `BacktestAnalytics`, `AnalyticsSummary`, `AnalyticsConfig`, `load_analytics_config`. 14 new tests: decision/confidence/risk distributions, embedded watchlist+strategy analytics, skipped-count aggregation, include_unknown toggle, empty scan, deterministic replay, immutable report, sorted-JSON serialization, config validation (unknown-key rejection, lowercase-level rejection, production config loads, missing fails loudly), and a real **BacktestRun end-to-end** produced by the M4.5 chain. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; scanner, watchlist manager, strategy framework, backtesting engine, workflow engine, and analytical engines all unchanged.

### M4.5 — Backtesting Engine

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Deterministic chronological replay of the existing operational pipeline across historical points, with no alternate analytical logic |
| Tests | 459 passed / 0 failed (19 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Backtesting Engine (`src/athena/backtest/`), which answers one question: "How would ATHENA's completed analytical pipeline and strategy framework have behaved across historical market snapshots?" `BacktestingEngine.run(points, *, run_id=None)` replays a chronological sequence of caller-supplied `ReplayPoint`s (each a timezone-aware `as_of`, a universe, and the per-instrument pipeline builder for that date — identical in shape to what the live scanner consumes) through the **existing** operational components: the M4.2 `DailyMarketScanner`, M4.3 `WatchlistManager`, and M4.4 `StrategyFramework` (which in turn run the M4.1 `WorkflowEngine` and the analytical core). It **orchestrates only** — it introduces no alternate analytical logic, computes no market values, and replays the same deterministic pipeline used live; the analytical core stays the single source of truth. Out-of-scope items (portfolio valuation, P&L, sizing, brokerage/slippage/cost simulation, order execution) are deliberately absent.

Each replay point produces an immutable `BacktestStep` referencing the artifacts the real pipeline emitted — scan id, watchlist snapshot id, strategy execution id, replay date, and execution timestamp — and retaining the full `DailyScanReport`, `WatchlistSnapshot`, and `StrategyExecution` for complete history preservation. Watchlist state **threads forward** chronologically (per `carry_watchlist` config) so trend-based watchlists and strategies observe prior scans exactly as they would live. Steps run in strict chronological order (sorted by `as_of`; duplicate timestamps fail loudly). **Failure isolation**: any step whose scan/apply/execute raises is recorded `FAILED` with a diagnostic note; with `continue_on_error` the replay proceeds (and a failed step does not advance carried state), otherwise it stops. Results aggregate into a `BacktestRun` (run identity + period + `BacktestSession`) carrying a `BacktestSummary` with sum-checked step counts and per-strategy `StrategyPerformance` (total matches, steps with matches, distinct instruments) across the whole period. Determinism verified: with `as_of` injected and no clock read, the same dataset yields an identical `to_dict()` on rerun (internal per-stage timings are excluded from serialization).

Files created: `src/athena/backtest/{__init__,models,engine}.py`, `config/backtest.json`, `tests/runtime/test_backtest.py`. Files modified: `src/athena/config/{models,loader,__init__}.py` (add `BacktestConfig`, `load_backtest_config`, exports). No analytical engine, scanner, watchlist manager, strategy framework, workflow engine, or frozen-domain type touched. Public APIs added: `BacktestingEngine`, `ReplayPoint`, `BacktestStep`, `BacktestSession`, `BacktestRun`, `BacktestSummary`, `StrategyPerformance`, `BacktestConfig`, `load_backtest_config`. 19 new tests: chronological ordering (incl. out-of-order input), all-steps-completed, step references, watchlist carry-forward (and disabled), multi-strategy performance aggregation, partial-failure isolation, stop-on-error, failed-step-doesn't-advance-state, deterministic rerun, empty dataset, immutable run, duplicate-replay-point rejection, history preservation, config validation (defaults, unknown-key rejection, production config loads, missing fails loudly), and a three-day **end-to-end replay** through the real workflow → scanner → watchlist → strategy chain. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; workflow engine, scanner, watchlist manager, strategy framework, and analytical engines all unchanged.

### M4.4 — Strategy Framework

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Deterministic framework for multiple strategies to select completed decision artifacts by policy, without any analytical calculation |
| Tests | 440 passed / 0 failed (19 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Strategy Framework (`src/athena/strategy/`), which answers one question: "Which completed ATHENA decisions satisfy each strategy's deterministic selection policy?" `StrategyFramework.execute(scan_report, watchlist, *, as_of)` runs every registered strategy over the immutable outputs of the M4.2 scanner (`DailyScanReport` → `DecisionReport`) and M4.3 watchlist manager (`WatchlistSnapshot`), producing an immutable `StrategyExecution`. It **coordinates strategy evaluation only** — it parses completed decision artifacts into read-only views, invokes each strategy, and aggregates; it never invokes an analytical engine, computes an indicator, or reinterprets a decision. Strategies express *selection*, not intelligence.

The `Strategy` contract (`base.py`) is a small ABC declaring `name`, `version`, `description`, and a pure `select(views) -> tuple[MatchProposal, ...]`. Each strategy sees only `InstrumentView`s — a pre-parsed, read-only lens bundling one instrument's completed decision facts (type, direction, and the score/confidence/risk values *already produced* by the core, read as-is, UNKNOWN preserved as `None`) with its current watchlist memberships. Five reference strategies (Momentum, Swing, Breakout, Mean Reversion, Sector Rotation) share a `ConfigurableStrategy` base that applies declarative `StrategyRuleCfg` filters (decision set, direction, watchlist overlap, min score, min confidence, max risk). A threshold set against an UNKNOWN value never matches — missing analytical values exclude an instrument rather than being defaulted (no fabrication). Multiple strategies may select the same instrument; overlaps are surfaced in the summary.

Determinism: instruments are viewed in stable sorted order, strategies run in registration order (and `from_config` registers enabled reference strategies in id-sorted order), and matches are ordered by instrument — with `as_of` injected and no clock read, identical inputs yield an identical `StrategyExecution` (verified via `to_dict` replay equality). Each `StrategyMatch` records the instrument, originating decision id, originating watchlist memberships, a strategy-specific explanation, and supporting references (decision id, scan id, watchlist snapshot id, and the score/confidence/risk refs lifted faithfully from the decision report). Duplicate strategy registration and unknown reference-strategy ids fail loudly; failed/skipped scan results are ignored.

Files created: `src/athena/strategy/{__init__,models,base,strategies,framework}.py`, `config/strategy.json`, `tests/runtime/test_strategy.py`. Files modified: `src/athena/config/{models,loader,__init__}.py` (add `StrategyConfig` + `StrategyRuleCfg`, `load_strategy_config`, exports). No analytical engine, scanner, watchlist manager, workflow engine, or frozen-domain type touched. Public APIs added: `StrategyFramework`, `Strategy`, `InstrumentView`, `MatchProposal`, `StrategyMatch`, `StrategyResult`, `StrategySummary`, `StrategyExecution`, the five reference strategies + `ConfigurableStrategy` + `REFERENCE_STRATEGIES`, `StrategyConfig`, `load_strategy_config`. 19 new tests: multiple strategies, overlapping matches, no matches, UNKNOWN-value exclusion, failed-results ignored, explanation + references preservation, registration, duplicate-registration rejection, `from_config` enabled-only + unknown-id rejection, deterministic replay, immutable output, empty universe, config validation (unknown decision, unknown direction, empty strategies, production config loads, missing config fails loudly), and a **real chain** consuming a scanner-produced `DailyScanReport` and a watchlist-manager-produced `WatchlistSnapshot`. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; scanner, watchlist manager, workflow engine, and analytical engines all unchanged.

### M4.3 — Watchlist Manager

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Maintain deterministic, explainable named watchlists derived exclusively from completed scan/decision artifacts |
| Tests | 421 passed / 0 failed (21 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Watchlist Manager (`src/athena/watchlist/`), which answers one question: "Which instruments deserve ongoing attention based on ATHENA's completed decisions?" `WatchlistManager.apply(scan_report, *, as_of, previous=None)` folds an immutable `DailyScanReport` (M4.2) into a new immutable `WatchlistSnapshot`. It **coordinates state only** — it never executes an analytical engine, never recalculates a decision, and never invents a conclusion; it reads only the completed decision outcomes already produced by the pipeline and scanner, and organises them into named watchlists.

Classification is entirely **configuration-driven** (`config/watchlist.json`, validated by `WatchlistConfig`). Two rule kinds cover the initial five watchlists: a `decision_in` rule (membership when the instrument's current decision type is in a configured set — **High Conviction** ← TRADE/INCREASE_POSITION, **Watch** ← WATCH/WAIT, **Rejected** ← NO_TRADE/AVOID_SECTOR) and a `trend` rule (membership by change in decision *strength* versus the previous scan, using a configurable `decision_rank` map — **Improving** when the rank rose, **Weakening** when it fell). An instrument may belong to several watchlists at once (e.g. both High Conviction and Improving).

`apply` is a **pure function** of `(config, previous, scan_report, as_of)`: no hidden state, no clock read (`as_of` injected), instruments processed in stable sorted order — so replaying the same scan sequence yields bit-identical snapshots (verified). Every membership change is recorded as an explained `WatchlistChange` (ADDED / RETAINED / REMOVED) stating *why the instrument entered, why it remained, or why it exited* (rule no longer satisfied, or absent from the current scan). `entered_as_of` is preserved across retentions so an entry's original entry time is never lost. `WatchlistHistory` is **append-only** — `record()` returns a new, extended history and never overwrites prior state. Failed/skipped scan results are ignored (only completed decisions classify); a scan report containing a duplicate instrument fails loudly.

Files created: `src/athena/watchlist/{__init__,models,manager}.py`, `config/watchlist.json`, `tests/runtime/test_watchlist.py`. Files modified: `src/athena/config/{models,loader,__init__}.py` (add `WatchlistConfig` + rule models, `load_watchlist_config`, exports). No analytical engine, scanner, workflow engine, or frozen-domain type touched. Public APIs added: `WatchlistManager`, `WatchlistSnapshot`, `WatchlistEntry`, `WatchlistChange`, `WatchlistChangeType`, `WatchlistHistory`, `WatchlistSummary`, `WatchlistConfig`, `load_watchlist_config`. 21 new tests: decision-in classification, multi-watchlist membership, additions/retention/removal (rule-lapse and absence), improving/weakening trends, no-trend-without-prior, append-only history + entry/exit explanation, deterministic replay, immutable snapshots, empty scan (and empty-scan removals), duplicate-instrument protection, failed/skipped results ignored, config validation (duplicate names, unknown decision, production config loads, missing config fails loudly), and a **real DailyScanReport** produced by the M4.2 scanner classified across two cycles. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; scanner, workflow engine, and analytical engines all unchanged.

### M4.2 — Daily Market Scanner

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Coordinate ATHENA's full analytical workflow across the approved universe into one immutable daily scan report |
| Tests | 400 passed / 0 failed (10 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Daily Market Scanner (`src/athena/scanner/`), which answers a single question: "What does ATHENA conclude today for every eligible instrument?" `DailyMarketScanner.scan(universe, *, as_of, pipeline_builder)` iterates the universe in **stable sorted order** (`sorted(set(universe))` — deterministic, deduplicated), asks the caller-supplied `pipeline_builder` for a per-instrument `InstrumentPlan`, executes that plan's `WorkflowDefinition` through the shared `WorkflowEngine`, and — after the workflow completes — reads the captured `ScanCapture` and renders a `DecisionReport` via the existing `DecisionReportingEngine`. It **coordinates only**: it reuses M4.1's engine and M3.7's reporting engine, invokes analytical engines exclusively inside workflow stages defined by the caller, and recalculates nothing.

The design challenge was that M4.1's `WorkflowExecution` (frozen, approved) does not surface the `DecisionOutcome`. Rather than modify the approved engine (which would need an ADR), the scanner uses a **capture pattern**: `InstrumentPlan` pairs the workflow definition with a `collect()` callable; workflow stages populate a closure, and the scanner calls `collect()` after `execute()` to retrieve the outcome. No M4.1 change, no frozen-domain change.

**Failure isolation** is total — every per-instrument step (build, execute, collect, report) is wrapped so one instrument's failure produces a `FAILED` result with a diagnostic note and never aborts the scan; a builder returning `None` yields `SKIPPED`. Results aggregate into an immutable `DailyScanReport` with `ScanStatistics` (sum-checked total/successful/failed/skipped) and a `ScanSummary` (decision-type distribution, frozen via `MappingProxyType`), plus `result_for()` lookup and a JSON-safe `to_dict()`. Determinism verified: two scanners under fixed clocks produce bit-identical `to_dict()`.

Files created: `src/athena/scanner/{__init__,models,scanner.py}`, `tests/runtime/test_scanner.py`. Files modified: none (pure addition; no engine or contract touched). Public APIs added: `DailyMarketScanner`, `DailyScanReport`, `InstrumentPlan`, `InstrumentScanResult`, `ScanCapture`, `ScanStatistics`, `ScanSummary`, `PipelineBuilder`. 10 new tests: multi-instrument scan, deterministic ordering, empty universe, partial-failure isolation, skipped instrument, failed result carries no report, replay determinism, immutability, `to_dict` shape, and a **real multi-instrument pipeline** wiring indicator → regime → scoring → decision engines through workflows. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed.

### M4.1 — Workflow Orchestration Engine

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Deterministic central orchestrator that runs analytical engines as coordinated pipeline stages |
| Tests | 390 passed / 0 failed (17 new) |
| Status | **APPROVED** — orchestration foundation for Phase 4 |
| Branch | main |

Built the runtime orchestration layer (`src/athena/runtime/`, realizing the blueprint's reserved §2 `runtime` module — building the plan, not a new module). `WorkflowEngine` executes a `WorkflowDefinition` (a validated DAG of `WorkflowStage`s) in a deterministic topological order, passing a read-only `WorkflowContext` accumulator through the stages; each stage's callable invokes an existing analytical engine and returns named outputs the engine merges (collisions rejected). It **coordinates only** — performs no analysis, duplicates no engine logic, modifies no engine. Dependency validation rejects missing dependencies, cycles, and duplicate stage names up front (`WorkflowError`). Failure isolation: a failed stage is recorded with its error and its downstream dependents are SKIPPED, while independent branches still run. Timing is captured per stage (offset + duration) via an **injected clock**, so under a fixed clock an execution is bit-identical — replay determinism verified. Produces an immutable `WorkflowExecution` (the execution report) plus a presentation-only `WorkflowReport` (`to_dict`/`to_json`/`to_text`). Verified end-to-end by wiring the real indicator → regime → scoring → decision engines as stages — the orchestrator ran the full pipeline without duplicating any engine.

Runtime types live in `src/athena/runtime/` — the blueprint's planned orchestration module — no ADR, no frozen-domain change, no analytical engine touched. Files created: `src/athena/runtime/{__init__,models,workflow,report}.py`, `tests/runtime/test_workflow.py`. Files modified: `src/athena/errors.py` (+WorkflowError). Public APIs added: `WorkflowEngine`, `WorkflowDefinition`, `WorkflowStage`, `WorkflowContext`, `WorkflowExecution`, `WorkflowReport`, `StageResult`, `ExecutionStatus`, `build_definition`. ruff clean; no drift; no tech debt.

---

## Phase 3 — Decision Intelligence (COMPLETE — pending formal review)

### M3.7 — Decision Trace & Reporting  (completes Phase 3)

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Presentation-only human- and machine-readable decision reports from immutable artifacts |
| Tests | 373 passed / 0 failed (11 new) |
| Status | **Awaiting owner approval** — closes Phase 3; Phase 4 blocked pending full Phase-3 review |
| Branch | main |

Built `DecisionReportingEngine` (`src/athena/reporting/`), completing Phase 3. It consumes a `DecisionOutcome` plus the source artifacts (scoring, confidence, risk, evidence bundle, indicators) and produces an immutable `DecisionReport` offering two views derived from the same source: `to_dict()`/`to_json()` (machine-readable, JSON-safe, sorted-key deterministic) and `to_text()` (human-readable, sectioned). The report faithfully mirrors the decision — decision summary/outcome/status/direction, trade-plan summary, all six gate results, score summary with component breakdown, confidence dimensions, risk dimensions, evidence summary (provenance + missing sources), indicator summary, full reasoning-stage trace, and referenced artifact ids. Presentation only: it never modifies, reinterprets, or recalculates any artifact, and adds no new conclusions. UNKNOWN is displayed explicitly for every absent artifact (verified on the INSUFFICIENT_DATA path). Pure and deterministic: no I/O, clock, or randomness; both views reproducible.

Report types live in `src/athena/reporting/` (not frozen domain §4) — no ADR. Files created: `src/athena/reporting/{__init__,models,engine}.py`, `tests/decision/test_reporting.py`. No config needed. Public APIs added: `DecisionReportingEngine.report`, `DecisionReport` (`to_dict`, `to_json`, `to_text`). Prior engines and frozen domain unchanged; ruff clean; no drift; no tech debt.

---

## Phase 3 — Decision Intelligence: COMPLETE (pending formal review)

All seven milestones implemented and individually reviewed: M3.1 Evidence Aggregation, M3.2 Indicator Engine, M3.3 Scoring, M3.4 Confidence, M3.5 Risk, M3.6 Decision, M3.7 Reporting. ATHENA now runs a complete, end-to-end, evidence-first decision pipeline: canonical data → market intelligence → aggregated evidence → objective indicators → transparent scores → confidence → risk → gated, auditable decisions → faithful human/machine reports. Every decision is deterministic, replayable, and traceable back to explicit evidence, measurements, and configuration; the frozen-domain TRADE invariant is enforced at construction. 373 tests, ruff-clean, zero technical debt. Ready for full Phase-3 review before Phase 4 is authorized.

---

### M3.6 — Decision Engine

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | First deterministic, auditable decisions combining scores + confidence + risk via config-driven gates |
| Tests | 362 passed / 0 failed (12 new) |
| Status | **Awaiting owner approval** — M3.7 (Decision Trace & Reporting) blocked until approved |
| Branch | main |

Built `DecisionEngine` (`src/athena/decision/`), the capstone that combines the analytical pipeline into the first explainable decisions. It consumes approved artifacts only (ScoringResult, ConfidenceAssessment, RiskAssessment, EvidenceBundle, RegimeResult, indicators, optional market/sector health) and produces the **frozen-domain** `Decision` + `DecisionTrace` wrapped in a `DecisionOutcome`. It evaluates all six §8.5 quality gates (DATA, EVIDENCE, RISK, EXPLAINABILITY, CONFIDENCE, MARKET) as `GateResult`s, then applies config-driven policy: TRADE (all gates pass + composite ≥ trade threshold + directional regime + buildable plan), WATCH (composite in watch band), NO_TRADE (below watch), or INSUFFICIENT_DATA (no composite). Every frozen invariant is honored — a TRADE always carries a `TradePlan`, a direction, and zero failed gates (verified end-to-end: a strong-bull pipeline yields TRADE with all six gates green). Trade plans use analytical levels only (last close ± ATR multiples for stop/target, constant risk-reward); `position_size` is a provisional unit — **no capital-based sizing** (deferred to the capital layer). The `DecisionTrace` records the full reasoning path (regime → market/sector health → evidence → score → confidence → risk → decision → trade_plan) with references. Pure and replayable: injected `as_of`, Decimal math, thresholds from `decision.json`; consumes approved artifacts, never recalculates lower layers or touches providers/repositories.

Engine + `DecisionOutcome` live in `src/athena/decision/` (the frozen `Decision`/`DecisionTrace` come from `athena.domain.decision` — no §4 change) — no ADR. Files created: `src/athena/decision/{__init__,models,engine}.py`, `config/decision.json`, `tests/decision/test_decision.py`. Files modified: `config/models.py` (+DecisionConfig and nested cfgs), `config/loader.py` + `config/__init__.py` (+load_decision_config). Public APIs added: `DecisionEngine.decide`, `DecisionOutcome`. Prior engines and frozen domain unchanged; ruff clean; no drift; no tech debt.

### M3.5 — Risk Engine

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Deterministic descriptive exposure assessment across six independent risk dimensions |
| Tests | 350 passed / 0 failed (16 new) |
| Status | **Awaiting owner approval** — M3.6 (Decision Engine) blocked until approved |
| Branch | main |

Built `RiskEngine` (`src/athena/risk/`). It consumes approved artifacts only and produces an immutable `RiskAssessment` of six independently explainable dimensions (higher value = more risk), each degrading to explicit `UNKNOWN`: volatility risk (regime volatility label), liquidity risk (Volume MA vs configured minimum), gap risk (regime gap label), event risk (CalendarContext expiries/scheduled events), market-environment risk (market-health labels mapped to risk points, averaged), and a concentration indicator (investable-universe breadth). Each dimension carries `RiskContribution` traces and a LOW/MEDIUM/HIGH level; the overall risk is a config-weighted mean over known dimensions with a `completeness` ratio and `unknown_stats`. Risk measures exposure only — independent of opportunity, and never a recommendation or position size. Missing artifacts produce transparent UNKNOWN; nothing is fabricated. Pure and replayable: injected `as_of`, Decimal math, all point maps from `risk_assessment.json` (a new file, kept separate from the F-4 no-trade rules in `risk.json`). Consumes approved artifacts, never providers/repositories.

Result types in `src/athena/risk/models.py` (not frozen domain §4) — no ADR. Files created: `src/athena/risk/{__init__,models,engine}.py`, `config/risk_assessment.json`, `tests/decision/test_risk.py`. Files modified: `config/models.py` (+RiskAssessmentConfig and nested cfgs), `config/loader.py` + `config/__init__.py` (+load_risk_assessment_config). Public APIs added: `RiskEngine.assess`, `RiskAssessment`, `RiskDimension`, `RiskContribution`, `RiskLevel`, `RiskStatus`. Prior engines and frozen domain unchanged; ruff clean; no drift; no tech debt.

### M3.4 — Confidence Engine

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Deterministic evaluation-reliability assessment across six independent confidence dimensions |
| Tests | 334 passed / 0 failed (17 new) |
| Status | **Awaiting owner approval** — M3.5 (Risk Engine) blocked until approved |
| Branch | main |

Built `ConfidenceEngine` (`src/athena/confidence/`). It consumes approved artifacts only — EvidenceBundle, ScoringResult, IndicatorResults — and produces an immutable `ConfidenceAssessment` of six independently explainable dimensions, each degrading to explicit `UNKNOWN`: evidence completeness (present vs required sources), data freshness (validation reports passed vs total), indicator availability (OK vs total), cross-engine agreement (dispersion of known component scores), unknown ratio (share of known artifacts), and consistency (absence of contradictory signals among known scores, config divergence gap). Each dimension carries `ConfidenceContribution` traces and a LOW/MEDIUM/HIGH level; the overall confidence is a config-weighted mean over known dimensions with a `completeness` ratio and `unknown_stats`. Confidence measures evaluation reliability only — never market direction, attractiveness, or risk. Missing artifacts transparently reduce confidence; nothing is fabricated or inferred. Pure and replayable: injected `as_of`, Decimal math, thresholds/weights from `confidence.json`; consumes approved artifacts, never providers/repositories.

Result types in `src/athena/confidence/models.py` (not frozen domain §4) — no ADR. Files created: `src/athena/confidence/{__init__,models,engine}.py`, `config/confidence.json`, `tests/decision/test_confidence.py`. Files modified: `config/models.py` (+ConfidenceConfig and nested cfgs), `config/loader.py` + `config/__init__.py` (+load_confidence_config). Public APIs added: `ConfidenceEngine.assess`, `ConfidenceAssessment`, `ConfidenceDimension`, `ConfidenceContribution`, `ConfidenceLevel`, `ConfidenceStatus`. Prior engines and frozen domain unchanged; ruff clean; no drift; no tech debt.

### M3.3 — Scoring Engine

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Transparent, config-driven component + composite scores from approved evidence and indicators |
| Tests | 317 passed / 0 failed (18 new) |
| Status | **Awaiting owner approval** — M3.4 (Confidence Engine) blocked until approved |
| Branch | main |

Built `ScoringEngine` (`src/athena/scoring/`). It consumes approved artifacts only — regime, market-health, sector-health assessments and `IndicatorResult`s — and produces six independent `ComponentScore`s (trend, momentum, market quality, sector quality, liquidity, technical structure), each 0–100 with a full `Contribution` trace referencing the exact regime/health dimension, indicator, and configured point value behind it, plus a plain-language explanation. A `CompositeScore` weights the known components (config weights sum to 100) and retains a complete `CompositeBreakdownItem` breakdown including each component's weight, value, and weighted contribution, with a `completeness` ratio. UNKNOWN propagation is strict: any missing evidence/indicator yields an explicit UNKNOWN component (no value, no fabricated default), unscoreable dimensions are excluded from averages, and the composite is UNKNOWN only when nothing is scoreable. Scores are intermediate artifacts — no buy/sell/hold, sizing, risk, or portfolio logic. Pure and replayable: injected `as_of`, Decimal math, all point maps from `scoring.json`; consumes approved artifacts, never raw providers/repositories.

Result types in `src/athena/scoring/models.py` (not frozen domain §4) — no ADR. Files created: `src/athena/scoring/{__init__,models,engine}.py`, `config/scoring.json`, `tests/decision/test_scoring.py`. Files modified: `config/models.py` (+ScoringConfig and nested cfgs), `config/loader.py` + `config/__init__.py` (+load_scoring_config). Public APIs added: `ScoringEngine.score`, `ScoringResult`, `ComponentScore`, `CompositeScore`, `CompositeBreakdownItem`, `Contribution`, `ScoreStatus`. Prior engines and frozen domain unchanged; ruff clean; no drift; no tech debt.

### M3.2 — Indicator Engine

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Deterministic technical-indicator measurement layer over canonical candles |
| Tests | 299 passed / 0 failed (26 new) |
| Status | **Awaiting owner approval** — M3.3 (Scoring Engine) blocked until approved |
| Branch | main |

Built `IndicatorEngine` (`src/athena/indicators/`) computing SMA, EMA, RSI (Wilder), ATR (Wilder), MACD, ADX (Wilder), and Volume MA from canonical candle data. Parameters are configuration-driven (`indicators.json`, extended with sma/macd/adx/volume_ma); calculations are pure Decimal functions in `calculations.py`; each result is an immutable `IndicatorResult` carrying name, status, parameters, window used, value(s), `IndicatorEvidence` (formula + inputs + explanation), and tz-aware ts. Insufficient history yields an explicit `UNKNOWN` result with no values (never a fabricated number). Strictly measurement-only — no signals, crossovers-as-events, composites, scoring, or interpretation; results never imply bullish/bearish/strength/weakness. Pure and replayable: injected `as_of`, deterministic Decimal math (fixed 28-digit context), candles sorted; provider/repository/intelligence-independent.

Result types in `src/athena/indicators/models.py` (measurement types, not frozen domain §4) — no ADR. Files created: `src/athena/indicators/{__init__,models,calculations,engine}.py`, `tests/decision/test_indicators.py`. Files modified: `config/indicators.json` (added sma/macd/adx/volume_ma params + versions; ema now single-period). Public APIs added: `IndicatorEngine.compute` / `compute_all`, `IndicatorName`, `IndicatorStatus`, `IndicatorResult`, `IndicatorEvidence`. Tests validate exact SMA/Volume-MA values, RSI boundaries (all-gains→100, all-losses→0, alternating≈50), ATR/MACD zero on flat/constant series, ADX range, Decimal precision, UNKNOWN handling, determinism, and immutability. Prior engines and frozen domain unchanged; ruff clean; no drift; no tech debt.

### M3.1 — Evidence Aggregation Engine

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Gather all approved intelligence into a single immutable, provenance-tagged evidence graph |
| Tests | 273 passed / 0 failed (10 new) |
| Status | **Awaiting owner approval** — M3.2 (Indicator Engine) blocked until approved |
| Branch | main |

Built `EvidenceAggregationEngine` (`src/athena/evidence/`), the first Decision Intelligence module. It gathers approved intelligence — regime, market health, sector health, universe, corporate-action evidence, and validation reports — into a single immutable `EvidenceBundle` of provenance-tagged `EvidenceItem`s. Each item records its `source`, `kind`, `reference_id`, timezone-aware `ts`, explanation, and the original (frozen) intelligence object as `payload` — so nothing is transformed or lost; provenance is preserved verbatim. The engine detects missing required sources (`required_sources` → `missing_sources`, `is_complete`) and publishes a per-source provenance count. Aggregation only — no scoring, signals, decisions, or transformation. Pure and replayable: injected `as_of`, deterministic fixed source ordering (sectors sorted), no I/O/clock/randomness; `EvidenceBundle` exposes `by_source`, `has_source`, `present_sources`.

Result types in `src/athena/evidence/models.py` (decision-intelligence types, not frozen domain §4) — no ADR. Files created: `src/athena/evidence/{__init__,models,engine}.py`, `tests/decision/test_evidence_aggregation.py`. Public APIs added: `EvidenceAggregationEngine.aggregate`, `EvidenceBundle`, `EvidenceItem`, `EvidenceSource`. All prior engines and frozen domain unchanged; ruff clean; no drift; no tech debt.

---

## Phase 2 — Market Intelligence (COMPLETE — pending formal review)

### M2.4 — Universe Engine  (completes Phase 2)

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Deterministic investable-universe construction via config-driven eligibility rules + constituent-breadth export |
| Tests | 263 passed / 0 failed (17 new) |
| Status | **Awaiting owner approval** — closes Phase 2; Phase 3 blocked pending full Phase-2 review |
| Branch | main |

Built `UniverseEngine` (`src/athena/universe/`). It evaluates each instrument independently against configuration-driven eligibility rules — active status, supported series, eligible exchange, data present, minimum trading history, minimum liquidity, and (when a calendar + window are supplied) data completeness — producing an immutable per-instrument `UniverseAssessment` (inclusion status, exclusion reasons, per-rule `RuleEvidence`, eligibility summary) and the frozen-domain `Universe` of included members (each with a full inclusion trace). Missing datasets produce explicit evidence, never silent exclusion. It also publishes **constituent advances/declines per sector** as a canonical output (`constituent_breadth`), completing the data dependency anticipated by Sector Health (M2.3) — computed from included instruments' latest vs prior close, and never by calling the Sector Health Engine. `max_universe_size` is advisory only (a hard cap would require ranking, which is out of scope) — all eligible instruments are included and the cap is surfaced in the summary. Pure and replayable (injected `as_of`, Decimal math, thresholds from `universe.json`); eligibility-focused, no ranking/scoring/selection.

Result types in `src/athena/universe/models.py` + `UniverseResult` in engine (not frozen domain §4; the canonical included set uses the frozen `Universe`/`UniverseMember`) — no ADR. Files created: `src/athena/universe/{__init__,models,engine}.py`, `tests/market_intel/test_universe.py`. Files modified: `config/models.py` (UniverseConfig +eligibility fields), `config/universe.json`. Public APIs added: `UniverseEngine.build`, `UniverseResult`, `UniverseAssessment`, `RuleEvidence`. Regime, Market Health, Sector Health, and frozen domain unchanged; ruff clean; no drift; no tech debt.

---

## Phase 2 — Market Intelligence: COMPLETE (pending formal review)

All four milestones implemented and individually reviewed: M2.1 Regime Engine, M2.2 Market Health, M2.3 Sector Health, M2.4 Universe Engine. The Market Intelligence layer now describes market conditions (regime, market health), sector conditions (sector health), and constructs a trustworthy investable universe — all deterministic, explainable, replayable, and strictly descriptive/eligibility-focused (no scoring, ranking, or decisions). Engines consume canonical data + approved intelligence and are aware-but-not-dependent on one another. 263 tests, ruff-clean, zero technical debt. Ready for full Phase-2 review before Phase 3 (Decision Intelligence) is authorized.

---

### M2.3 — Sector Health Engine

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Descriptive per-sector condition across four independently explainable dimensions |
| Tests | 246 passed / 0 failed (23 new) |
| Status | **Awaiting owner approval** — M2.4 (Universe Engine) blocked until approved |
| Branch | main |

Built `SectorHealthEngine` (`src/athena/sector_health/`). Per sector it consumes canonical sector-index `Candle` history (plus optional constituent breadth) and produces an immutable `SectorHealthAssessment` of four independently explainable dimensions, each degrading to explicit `*_UNKNOWN`: **trend** (fast/slow SMA → UPTREND/DOWNTREND/SIDEWAYS), **breadth** (constituent participation — reported `SECTOR_BREADTH_UNKNOWN` unless constituent advances/declines are supplied; never inferred, since constituent data arrives with M2.4), **momentum** (period ROC), and **volatility** (realized volatility = stdev of returns, a sector-specific context that complements — not duplicates — Market Health). `assess_many` evaluates multiple sectors deterministically. Every dimension emits `SectorHealthEvidence` with inputs, thresholds, outcome, and explanation. Pure and replayable (injected `as_of`, Decimal math incl. `Decimal.sqrt`, thresholds from `sector_health.json`); descriptive only — no ranking, rotation, selection, or signals. Regime-aware and Market-Health-aware but dependent on neither (optional, explanation-only).

Result types in `src/athena/sector_health/models.py` (not frozen domain §4) — no ADR. Files created: `src/athena/sector_health/{__init__,models,engine}.py`, `config/sector_health.json`, `tests/market_intel/test_sector_health.py`. Files modified: `config/models.py` (+SectorHealthConfig and nested cfgs), `config/loader.py` + `config/__init__.py` (+load_sector_health_config). Public APIs added: `SectorHealthEngine.assess` / `assess_many`, `SectorHealthResult`, `SectorHealthAssessment`, `SectorHealthEvidence`, `SectorHealthLabel`, `SectorHealthConfig`, `load_sector_health_config`. Regime, Market Health, and frozen domain unchanged; ruff clean; no drift; no tech debt.

### M2.2 — Market Health Engine

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Descriptive assessment of overall market condition across four independently explainable dimensions |
| Tests | 223 passed / 0 failed (24 new) |
| Status | **Awaiting owner approval** — M2.3 (Sector Health) blocked until approved |
| Branch | main |

Built `MarketHealthEngine` (`src/athena/market_health/`). It consumes canonical `Candle` history + optional `MarketSnapshot`, and produces an immutable `MarketHealthAssessment` composed of four independently explainable dimensions, each always labelled (explicit `*_UNKNOWN` on insufficient data): **breadth** (advance ratio from snapshot advances/declines), **trend quality** (one-directional consistency of recent index returns — complements the Regime Engine's direction, does not replace it), **momentum** (period rate-of-change of the index), and **volatility** (contextual read of India VIX on market stability, framed as health not re-classification). Every dimension emits `HealthEvidence` carrying inputs, the thresholds that produced the label (owner suggestion #3), the outcome, and a human explanation. Pure and replayable (injected `as_of`, Decimal math, thresholds from `market_health.json`); descriptive only — no scores, rankings, or recommendations. Regime-aware but not regime-dependent: an optional `RegimeResult` enriches the trend-quality explanation only; labels are identical with or without it (verified by test).

Result types live in `src/athena/market_health/models.py` (market-intelligence types, not frozen domain §4) — no ADR. Files created: `src/athena/market_health/{__init__,models,engine}.py`, `config/market_health.json`, `tests/market_intel/test_market_health.py`. Files modified: `config/models.py` (+MarketHealthConfig and nested cfgs), `config/loader.py` + `config/__init__.py` (+load_market_health_config). Public APIs added: `MarketHealthEngine.assess`, `MarketHealthResult`, `MarketHealthAssessment`, `HealthEvidence`, `MarketHealthLabel`, `MarketHealthConfig`, `load_market_health_config`. Regime Engine and frozen domain unchanged; ruff clean; no drift; no tech debt.

### M2.1 — Regime Engine

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Deterministic market-regime classification from canonical market data; descriptive, not prescriptive |
| Tests | 199 passed / 0 failed (17 new) |
| Status | **Awaiting owner approval** — M2.2 (Market Health) blocked until approved |
| Branch | main |

Built `RegimeEngine` (`src/athena/regime/`), the first Market Intelligence module. It consumes canonical `Candle` history (an index) plus an optional `MarketSnapshot` (India VIX) and produces the frozen-domain `RegimeAssessment` plus a supporting `RegimeEvidence` chain. Three orthogonal, deterministic dimensions, each always labelled (explicit `*_UNKNOWN` when data is insufficient — never a silent omission): **trend** (BULL/BEAR/SIDEWAYS via fast-vs-slow SMA and last close), **volatility** (HIGH/LOW/NORMAL via India VIX against configured bands), and **gap** (UP/DOWN/NONE via latest open vs prior close against the gap threshold). Pure and replayable: no I/O, no clock reads (time injected as `as_of`), no randomness; Decimal math throughout; thresholds from the existing `regime.json`. Output is strictly descriptive — labels, evidence, and explanation only; no scoring, ranking, or recommendation.

Regime result types live in `src/athena/regime/models.py` (market-intelligence types, not additions to frozen domain §4, which already provides `RegimeAssessment`) — no ADR required. Files created: `src/athena/regime/{__init__,models,engine}.py`, `tests/market_intel/test_regime.py`. Public APIs added: `RegimeEngine.assess`, `RegimeResult`, `RegimeEvidence`, `RegimeLabel`. Validation checklist passed; frozen contracts unchanged; ruff clean; no drift; no tech debt.

---

## Phase 1 — Data Foundation: COMPLETE ✅ (approved 2026-07-20)

All six milestones implemented and individually reviewed: M1.1 provider contracts, M1.2 FileProvider, M1.3 validation layer, M1.4 corporate actions, M1.5 SQLite repository, M1.6 backup & restore. The data foundation now ingests (via an abstract, order-incapable provider), validates, historically adjusts, persists, and recovers canonical market data — deterministically, explainably, and replayably. 182 tests, ruff-clean. **Phase 1 approved; Phase 2 (Market Intelligence) authorized.**

---

### M1.5 — SQLite Repository

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Persistent storage layer: schema, repository, WAL/FK config, integrity verification, quarantine + corporate-action persistence |
| Tests | 171 passed / 0 failed (23 new) |
| Status | **Awaiting owner approval** — M1.6 (backup & restore) blocked until approved |
| Branch | main |

Built `SqliteRepository`, ATHENA's persistent ledger. Deterministic schema (ATHENA-002 §5) with a single `candles` table keyed by (instrument_id, timeframe, ts_open) serving both daily and intraday, plus `instruments`, `quotes`, `market_snapshots`, `corporate_actions`, `quarantine_records`, and a `schema_version` table for future migrations. Explicit primary keys, foreign keys, and a range index; all decimals/timestamps stored as TEXT (ISO-8601, tz-aware) to preserve exact precision. SQLite configured with WAL mode and enforced foreign keys per connection; writes wrapped in transactions with a public `transaction()` context manager (commit on success, rollback on exception). Repository returns canonical domain objects, never rows — no provider, validation, or intelligence logic lives here. Append-only history (duplicate primary keys rejected as `RepositoryError`); instruments and quarantine support idempotent upsert. `verify_integrity()` runs `PRAGMA integrity_check` + `PRAGMA foreign_key_check` + schema-version check and returns an immutable `IntegrityReport`; corrupt/non-SQLite files fail loudly. Quarantine persistence serializes/restores `QuarantineRecord`s with full validation evidence, timestamps, types, severities, and explanations.

Storage types live in `src/athena/data/store/` — §5 schema is not among the §19-frozen items, and the milestone checklist confirms no ADR — so schema evolution is allowed within the data module. Files created: `src/athena/data/store/{__init__,schema,serialization,repository}.py`, `tests/data_layer/test_repository.py`. Files modified: `src/athena/errors.py` (+RepositoryError), `.gitignore` (WAL sidecars + db/). Public APIs added: `SqliteRepository` (initialize, upsert_instrument, get_instrument, list_instruments, add_candles, get_candles, add_quotes, get_quotes, add_snapshot, get_latest_snapshot, add_corporate_action, get_corporate_actions, save_quarantine, get_quarantine, list_quarantine, verify_integrity, transaction, close), `IntegrityReport`, `SCHEMA_VERSION`. Validation checklist 1–10 passed; provider contract, Validation Layer, and Corporate Actions Engine untouched; no drift; no tech debt.

### M1.4 — Corporate Actions Engine

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Provider/storage-independent modeling + deterministic back-adjustment for splits, bonuses, dividends, renames |
| Tests | 148 passed / 0 failed (19 new) |
| Status | **Awaiting owner approval** — M1.5 (SQLite repository) blocked until approved |
| Branch | main |

Built a Corporate Actions Engine that interprets the canonical (frozen) `CorporateAction` domain object into validated typed actions (`Split`, `Bonus`, `Dividend`, `Rename`) and applies deterministic back-adjustment to candle datasets, producing **adjusted copies** with full evidence — originals are never mutated (and `Candle` is frozen regardless). Standard model: an action with ex_date D adjusts only candles strictly before D; split from→to scales price by from/to and volume by to/from; bonus b:h scales price by h/(h+b); dividend scales price by (prev_close − amount)/prev_close using the raw close before D; factors are cumulative across sequential actions; renames map identifiers (with chain resolution A→B→C) and never touch candle values. Four explicit, traceable strategies (RAW, SPLIT_ADJUSTED, SPLIT_BONUS_ADJUSTED, FULLY_ADJUSTED) — no hidden behavior. Every adjustment emits immutable `AdjustmentEvidence` (action, ex_date, price/volume factor, affected record count, explanation, metadata); the whole run returns an immutable `AdjustmentResult`. Deterministic Decimal math (fixed context) and injected `as_of` make it fully replayable. Optional Calendar Engine only annotates whether an ex_date is a trading session — effective dates are never inferred. No fetching, no persistence, no provider/file/SQLite awareness.

Engine types live in `src/athena/data/corporate_actions/` — not additions to the frozen domain §4 — so no ADR was required. Files created: `src/athena/data/corporate_actions/{__init__,models,evidence,engine}.py`, `tests/data_layer/test_corporate_actions.py`. Files modified: `src/athena/errors.py` (+CorporateActionError). Public APIs added: `CorporateActionsEngine` (`adjust`, `build_symbol_map`, `resolve_symbol`), `parse_action`, `Split`/`Bonus`/`Dividend`/`Rename`, `CorporateActionType`, `AdjustmentStrategy`, `AdjustmentEvidence`, `AdjustmentResult`. Validation checklist 1–10 passed; provider contract and Validation Layer untouched; no drift; no tech debt.

### M1.3 — Validation Layer

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Provider-independent data-quality framework: freshness, OHLC, duplicate, gap validation; immutable reports; quarantine |
| Tests | 129 passed / 0 failed (25 new) |
| Status | **Awaiting owner approval** — M1.4 (corporate actions) blocked until approved |
| Branch | main |

Built a reusable validation framework that operates exclusively on canonical `Candle` objects and the Phase-0 Calendar Engine — no file/SQLite/broker/provider awareness. Validators are pure functions with an injected `as_of` (no clock reads → deterministic and replayable). Freshness compares daily data against the calendar's expected latest trading day and intraday data against the reference time, with configurable thresholds. OHLC validation checks the one business rule the Candle contract does NOT guarantee — strictly positive prices — and explicitly does not re-check H/L ordering (structurally enforced by the domain object) to avoid duplicating provider responsibility. Duplicate detection targets cross-dataset/ingestion-boundary duplicates (provider within-request dedup untouched). Gap detection uses the Calendar Engine for both missing trading sessions (weekends/holidays never counted) and missing intraday intervals; sessions are never inferred manually. Every check produces an immutable `ValidationReport` (type, result, severity, explanation, evidence, statistics, tz-aware timestamp); `DatasetValidator` aggregates into an immutable `ValidationSummary`; `QuarantineRegistry` records invalid datasets with preserved failure evidence and never auto-repairs.

Validation types live in `src/athena/data/validation/` — data-layer result types, NOT additions to the frozen canonical domain model (§4) — so no ADR was required. Files created: `src/athena/data/validation/{__init__,reports,validators,dataset_validator,quarantine,calendar_expectations}.py`, `config/validation.json`, `tests/data_layer/test_validation.py`. Files modified: `config/models.py` (+ValidationConfig/FreshnessConfig/GapConfig), `config/loader.py` + `config/__init__.py` (+load_validation_config). Public APIs added: `DatasetValidator`, `ValidationReport`, `ValidationSummary`, `ValidationType`, `ValidationResult`, `Severity`, `QuarantineRegistry`, `QuarantineRecord`, the five `validate_*` functions, `load_validation_config`, `ValidationConfig`. Validation checklist 1–10 passed; provider contract untouched; no drift; no tech debt.

### M1.2 — FileProvider

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | First production `MarketDataProvider`, backed by local CSV/JSON files; reference implementation for all future providers |
| Tests | 104 passed / 0 failed (37 new) |
| Status | **Awaiting owner approval** — M1.3 (validation layer) blocked until approved |
| Branch | main |

Implemented `FileProvider` conforming 100% to the frozen contract (passes the M1.1 suite unchanged). Loads daily candles, intraday candles, instrument metadata, market snapshots, and quotes from configurable file locations (`config/providers/file.json`, loaded via a new `load_file_provider_config` + `FileProviderConfig` model — `AthenaConfig` untouched, so config compatibility is preserved). Deterministic: no caching, no mutable global state, no clock reads, no concurrency; candles sorted ascending and deduplicated to honor the contract. Decimal precision and tz-aware timestamps preserved end to end. Error taxonomy differentiates missing files, invalid format (wrong header), unsupported instrument/timeframe/capability, and corrupted data (non-numeric values, impossible OHLC, naive timestamps, duplicate timestamps) — all `ProviderError` with file:line context. Validation is limited to what loading correctness requires; freshness/gap/cross-dataset validation deferred to M1.3 as instructed.

Files created: `src/athena/data/__init__.py`, `src/athena/data/providers/__init__.py`, `src/athena/data/providers/file_provider.py`, `config/providers/file.json`, two deterministic fixture datasets (`tests/data/fileprovider/` synthetic, `tests/data/fileprovider_sample/` sanitized-realistic with real symbols/ISINs but fictional prices), `tests/contract/test_file_provider_contract.py`, `tests/data_layer/test_file_provider.py`, dataset READMEs. Files modified: `config/models.py` (+FileProviderConfig, ProviderCapabilitiesConfig), `config/loader.py` + `config/__init__.py` (+loader). Public APIs added: `FileProvider`, `FileProvider.from_config_dir`, `load_file_provider_config`, `FileProviderConfig`. Validation checklist 1–10 passed; contract unchanged; no ADR; no drift; no tech debt.

### M1.1 — MarketDataProvider Contracts

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Provider Protocol behavioral contract, ProviderCapabilities/ProviderHealth invariants, reusable contract test suite |
| Tests | 67 passed / 0 failed (16 new) |
| Status | **Awaiting owner approval** — M1.2 (FileProvider) blocked until approved |
| Branch | main |

Frozen Protocol signatures untouched (contract compatibility preserved). Added: constructor invariants on `ProviderCapabilities` (non-empty unique timeframes, history ≥ 1 day) and `ProviderHealth` (mandatory detail, tz-aware timestamps); a documented behavioral contract on the Protocol (capability honesty, candle ordering/uniqueness/range, emptiness-is-not-error, determinism, unknown-id failures, structurally-forbidden order methods); `tests/contract/provider_contract.py` — the conformance suite every provider (M1.2 FileProvider, future broker adapters per DD-1) must pass unchanged, including a `test_no_order_methods_exist` structural-safety check; proven against a deterministic in-memory `StubProvider` (test infrastructure only, arithmetic data, no randomness/clock reads) plus negative tests showing the suite catches rogue order methods and invalid capabilities. Validation checklist 1–10 passed; no ADR needed; no config changes.

---

## Phase 0 — Foundations

| | |
|---|---|
| Completed | 2026-07-20 |
| Blueprint scope | ATHENA-002 §14, Phase 0 |
| Tests | 51 passed / 0 failed |
| Status | **APPROVED** (owner + principal engineer review passed, 2026-07-20) |
| Branch | main |
| Lessons learned | Phase-sized batches are too large to review well — milestone-based workflow adopted from Phase 1 (see CLAUDE.md, docs/MILESTONES.md) |

### 1. Summary of completed work

Project scaffolding (`pyproject.toml`, `justfile`, `.env.example`); complete canonical domain model; layered configuration framework with strategy profiles, feature flags, and cross-file invariants; JSONL logging with secret redaction and run/cycle correlation; observability skeleton (metric timers, performance-budget violations, system-health pre-flight); Trading Calendar Engine loaded with the real NSE 2026 holiday calendar (16 weekday holidays + Muhurat on 2026-11-08); CLI commands `athena today`, `athena health`, `athena version`.

### 2. Architectural compliance review

All Phase 0 exit criteria pass: CalendarContext correct for the 10 acceptance dates including Republic Day (holiday) and Muhurat (special session overriding a Sunday, timings honestly "TBD" until NSE notifies); config invariant violations fail with readable errors naming field and rule; full suite green. Contracts match the blueprint exactly: PipelineContext enforces consumes/produces discipline (re-producing a key raises, F-1/ADR-003); `MarketDataProvider` Protocol contains no order methods (ADR-002); explanations are constructor-mandatory — a TRADE decision without a TradePlan, without a direction, or with a failed quality gate cannot be instantiated (F-12, ADR-005); prices are Decimal; timestamps are timezone-aware; clocks are injected. No architectural deviations; no ADR was needed.

### 3. Files created

- `src/athena/domain/` — enums, market, evidence, decision, run, health, context, interfaces (8 files)
- `src/athena/config/` — models (pydantic), loader + snapshot hashing (2 files)
- `src/athena/observability/` — logging, metrics, health (3 files)
- `src/athena/calendar/engine.py`, `src/athena/cli.py`, `src/athena/errors.py`
- `config/` — base, market.nse, risk, capital, regime, universe, indicators, profiles/intraday-momentum, calendar/{holidays,expiries,events} (10 files)
- `tests/` — conftest + 5 test modules + golden-dataset skeleton README
- Scaffolding: `pyproject.toml`, `justfile`, `.env.example`

### 4. Tests added (51)

Calendar acceptance (10 parametrized dates, timings, trading-session semantics, budget event, fail-loud on uncovered year, determinism); config (11 cases: invariants, typo rejection, missing file, unknown profile, unversioned indicator, out-of-session trading window, snapshot hash determinism and change-sensitivity); domain invariants (immutability, impossible OHLC, naive timestamps, mandatory explanations, score-breakdown sum, decision contract, context discipline, read-only context data); observability (JSON-line shape, run/cycle correlation, secret redaction, budget violation detection, health pre-flight honest WARNs, calendar-coverage BLOCKED); CLI (5 commands/paths).

### 5. Remaining work

Phase 1 (Data): `MarketDataProvider` contract test suite, FileProvider (EOD bhavcopy + intraday files), validation layer (freshness, OHLC sanity, gaps, duplicates), corporate-actions handling, SQLite store with backup/restore. Owner actions before relying on calendar-aware features: verify `config/calendar/holidays.json` against the NSE circular and set `verified_by_owner: true`; populate `config/calendar/expiries.json` from the current derivatives circular (left empty by design — expiry weekdays change by circular and were not guessed).

### 6. Risks discovered

The AI sandbox cannot delete files, so `athena health` reports storage/logs BLOCKED when run there — the check is working as designed and passes on the owner's machine. The blueprint pins Python ≥ 3.12 but verification ran on 3.10; `pyproject.toml` currently declares ≥ 3.10 — tighten to 3.12 once the production interpreter is confirmed.

### 7. Suggested improvements (implementation-only)

A `just verify-calendar` target that diffs `holidays.json` against the NSE circular each January; a minimal GitHub Actions workflow (ruff + mypy + pytest) once the owner wants CI on pushes.
