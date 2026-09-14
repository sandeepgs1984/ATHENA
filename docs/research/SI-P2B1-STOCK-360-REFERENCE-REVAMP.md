# SI-P2B.1 — Stock 360 Reference-Matched Visual Revamp

**Status:** Implemented, presentation-only, on asset `9.264.0`. Owner review
pending. SI-P2B's own frozen contract (`docs/research/SI-P2B-STOCK-360-IMPLEMENTATION.md`)
is unchanged — this is a visual/UX revamp of that same Stock 360 surface,
not a new methodology or DTO change.

## Context

After several incremental UX passes on the Stock 360 tab this same day (sticky
section-nav bar, compact scan-strip chips, de-duplicated Technical/Momentum
content), the owner supplied a polished external reference mock and asked for
an exact-UX match, planned properly before further ad-hoc changes. The full
plan (real-data-vs-placeholder ledger, palette decision, section-by-section
scope) was written, the owner answered two clarifying questions, and the plan
was approved before implementation. The D1 chart card and the global app-shell
sidebar were explicit non-goals throughout.

**Owner decisions locked in:**
- Keep the reference's decorative flourishes (hero side panel, sector icon,
  cap-tier tag), but label every one explicitly as real vs. placeholder so a
  future pass can wire in real data with a one-line grep.
- Adopt the reference's richer, scoped color palette for Symbol Intelligence
  specifically (gradient fills, multi-color chips) — a deliberate, documented
  exception, not a change to the rest of the dashboard's tokens.

## Real data vs. decorative placeholder — the ledger

| Element | Status | Notes |
|---|---|---|
| Symbol, name, exchange, price, change %, as-of dates | Real | Already wired |
| Decision badge, confidence, score, gates, explanation | Real | Already wired |
| Sector tag | Real | `identity.sector`; shown only when present |
| Sector-derived icon | Real-derived | Small lookup table keyed on sector text, not a per-company logo (no such field exists) |
| ₹ absolute price change | Real-derived | `live.last_price − live.previous_close`, both real |
| Market-cap tier ("Cap tier — pending") | **Placeholder** | No `market_cap`/`cap_tier` field exists anywhere in the backend; rendered as a visibly dashed/muted pill, never a fabricated tier |
| Hero side panel | **Placeholder** | CSS gradient panel + one static line in ATHENA's own voice ("Evidence-led. Always explainable."), not a stock photo |
| Price Map ladder color track | Real positions, stylistic color | Level values are 100% real; the red→green track is a positional "lower ↔ higher price" spectrum only, never a buy/sell or safety signal |
| ATHENA View score gauge gradient | Real score, stylistic color | Same positional-magnitude framing as the ladder |
| DarvaX card background pattern | **Placeholder, deliberately abstract** | A generic diagonal-line texture, never shaped like a real chart of the instrument — the card's own copy explicitly states DarvaX evidence isn't mixed into Stock 360 |
| "Technical Detail" card | **Removed** | Duplicated the scan strip's own Structure/SuperTrend signals; SMA20/50 values remain visible in the untouched chart's own legend |

## What shipped

- **Identity hero** (`siHeader`): sector-derived circular icon avatar, a tag
  row (exchange/instrument, conditional real sector, dashed cap-tier
  placeholder), a richer ₹-and-% price-change badge, and a decorative
  gradient side panel (hidden under 960px).
- **Scan strip** (`siScanStrip`/`siSignalChip`): icon-chip treatment for the
  5 existing signals (Structure, SuperTrend, RSI, Volume, Decision).
- **Portfolio Context** (`siPortfolioCard`): a status pill, a 6-tile grid
  (Quantity/Average/Last/Investment/Current Value/P&L), and a colored
  callout footer reusing the existing interpretation/next-action text.
- **Price Map**: rebuilt from stacked rows into a horizontal ladder
  (`siPriceLadderPoints`/`siPriceLadder`) — every marker is a real structural
  level positioned by its real value on a shared min–max scale.
- **ATHENA View** (`siAthenaView`): icon stat-tiles for Confidence/Plan
  Freshness, and a real gradient 0–100 score gauge (a magnitude scale, not a
  signal).
- **DarvaX card**: a proper "Experimental" pill badge and the abstract
  background pattern.
- **Removed**: the duplicate Technical Detail card (`siTechnicalCard`) and its
  call site, plus `siStat`, `siStructureDiffers`, `siMetric`, and all their
  now-orphaned CSS (`.si-technical-*`, `.si-stat-strip`, `.si-level-*`,
  `.si-metric*`), confirmed dead via `grep` before deletion.
- **New Symbol-Intelligence-only palette** (`--si-gradient-cool`,
  `--si-gradient-scale`), documented at the top of
  `15-symbol-intelligence.css` as a deliberate, scoped exception — no other
  tab's tokens changed.
- **Density**: `.si-360-stack` (Price Map + ATHENA View) changed from a
  full-width single column to a responsive side-by-side row on wide
  viewports, closing most of the gap against the reference's compact
  dashboard-grid feel.

## Defects found and fixed during verification

Real, user-facing bugs caught by testing against actual data shapes rather
than trusting the first render:

1. **Ladder dots not on the track.** The dot was the second child in a
   top-anchored flex column under its label card, so its position depended
   on the card's own height instead of the track. Fixed by centering each
   `.si-ladder-point` exactly on the track's vertical midline (matching the
   existing correct close-price marker) and floating the card above it via
   absolute positioning — the dot can no longer drift regardless of card
   height or tier.
2. **Overlapping labels for coincident/near-coincident levels.** Two levels
   sharing an exact price (a real, observed case: Review Trigger and
   Target 1 landing on the same value) rendered as stacked, unreadable text.
   Fixed with a 3-tier vertical stagger (cycled by sorted position), keeping
   any two same-tier points at least 3 sort-positions apart.
3. **No layout fits every viewport.** Below ~720px there isn't enough
   horizontal room for any tier count to avoid collisions with up to 7 real
   levels. The ladder now falls back to a plain wrapping card list on narrow
   viewports — no absolute positioning, no spectrum track, guaranteed no
   overlap.
4. **Fabricated `₹0.00` "Available High" point.** `siFiniteNumber(null)`
   coerces via `Number(null) === 0`, which is finite — so a genuinely absent
   `available_history_high` rendered as a real-looking zero-value point.
   Fixed with a new `siNullableFiniteNumber` helper scoped to the price-map's
   plain scalar fields (zone objects were already correctly guarded by
   `siZoneLooksEmpty`).

All four were verified fixed with pixel-level collision detection (not just
screenshots) across three real data shapes: a tied-value case matching the
owner's own reported ACMESOLAR data, a 7-distinct-level case, and mobile
width — zero collisions in all three, dots confirmed exactly on the track.

## Explicit non-goals (unchanged)

- The D1 chart card itself (rendering, window toggle, legend, tooltips) —
  zero changes.
- The global app-shell sidebar — untouched.
- Backend/DTO/schema changes — nothing here adds a persisted field; every
  "real-derived" element computes from fields that already exist.

## Files touched

- `src/athena/api/static/js/08c-symbol-intelligence.js`
- `src/athena/api/static/css/15-symbol-intelligence.css`
- `src/athena/api/static/index.html`, `src/athena/api/static/dashboard.css`
  (asset cache pin only)
- `tests/symbol_intelligence/test_si_p2a_experience.py`,
  `tests/symbol_intelligence/test_si_p2b_stock_360.py`,
  `tests/api/platform/test_dashboard_hosting.py`,
  `tests/api/platform/test_decision_chart_release_gate.py`

## Verification

- `python3 -m pytest tests/symbol_intelligence/ tests/api/platform/test_dashboard_hosting.py tests/api/platform/test_decision_chart_release_gate.py -q`
  → 95 passed, 1 pre-existing failure unrelated to this work
  (`test_si_p2e_no_decision_and_invalid_symbol_are_distinct`, owned by the
  concurrent SI-P2E track).
- Visual verification via an isolated throwaway server (scratch config +
  empty DB, single-user bypass — never the owner's real `db/athena.db`),
  with synthetic bundles covering: sector present/absent, portfolio
  held/not-held, decision present/absent, empty Price Map levels, tied
  Price Map values (matching the owner's own reported data), a 7-distinct-
  level case, and mobile width (375px) — screenshotted and pixel-collision-
  checked at each state.
- `node --check` and a brace-balance check after every CSS/JS edit.

## Known gaps vs. the reference mock — handoff for further work

The owner compared a live screenshot of this implementation directly against
the reference mock after this milestone shipped and found the page still
reads noticeably sparser/less dense than the reference, beyond the three
rendering defects fixed above. This section is the honest, itemized list of
what's still different, for whoever picks up the next pass — **do not
assume this milestone is a pixel-exact match**. Each item below is
structural/layout, not a data-correctness bug (those are covered above).

### A. Real gaps worth closing

1. **Page composition order differs from the reference.** The reference
   puts the "Recent Price Action" chart card immediately after the identity
   hero (the second major element on the page). This implementation's DOM
   order (`renderSymbolIntelligence` in `08c-symbol-intelligence.js`) is:
   coverage banner → scan strip → Price Map + ATHENA View → **chart** →
   Research Brief → Portfolio + Capability + DarvaX. The chart sits much
   further down the page than in the reference. Moving the chart earlier in
   the template is a pure ordering change (the chart card's own internals —
   rendering, window toggle, legend, tooltips — remain the explicit
   non-goal from the original plan and must stay untouched); it was not
   attempted this milestone because the owner's original instruction was
   "exclude chart section revamp" and reordering surrounding cards around a
   fixed chart position felt safer to scope conservatively. Revisit with the
   owner before moving it.
2. **The chart card has no side glance-stat panel.** The reference's chart
   card includes a compact 3-row "Trend / Momentum / Volume" panel to the
   right of the chart (icon + label + value), inside the same card. This
   implementation instead surfaces that information as a separate, full-
   width 5-chip scan strip (`siScanStrip`) positioned well above the chart.
   The scan strip carries genuinely more information (Structure, SuperTrend,
   RSI, Volume, Decision — 5 signals vs. the reference's 3), so collapsing
   it into the chart's side panel is a real design decision for a future
   milestone, not a small tweak — it needs to decide whether all 5 signals
   move into the chart card or whether the scan strip stays separate and
   only a subset joins the chart.
3. **Card grouping doesn't match the reference's two 3-column rows.** The
   reference groups cards as: Row 1 = Research Brief + Portfolio Context +
   Capability Availability (3 columns); Row 2 = Price Map + ATHENA View +
   DarvaX (3 columns). This implementation groups them differently: Research
   Brief is its own full-width collapsible `<details>` section
   (`.si-written-summary`, unchanged from SI-P2D and out of this
   milestone's scope to restructure); `.si-360-stack` (Price Map + ATHENA
   View, now 2 columns after this milestone's density fix) does not include
   DarvaX; and `.si-360-secondary` (Portfolio + Capability + DarvaX, 3
   columns) has DarvaX where the reference doesn't. Matching the reference
   exactly means moving DarvaX from `.si-360-secondary` into `.si-360-stack`
   and deciding whether Research Brief becomes a true grid sibling of
   Portfolio/Capability or stays a full-width `<details>` above them — a
   moderate `renderSymbolIntelligence` template restructure, not just a CSS
   change.
4. **Header lacks the reference's tagline.** The reference shows "Deep
   Insights. Smarter Decisions." under the "Symbol Intelligence" title, and
   a closing footer with "Better information. Better decisions. A better
   you." plus a small "Symbol Intelligence v2 | Live Data · Evidence Driven"
   version line. Neither exists in this implementation. Low effort, purely
   cosmetic, not attempted this milestone since it touches shared app-shell
   header markup (`index.html`/`03-app-shell.js`), not the SI-scoped files
   this milestone stayed within.
5. **Identity tag row styling differs.** The reference renders
   `NSE:ACMESOLAR | Renewable Energy | Mid Cap` as plain pipe-separated text
   with no borders. This implementation renders each as a separate bordered
   pill (`.si-id-meta-tag`). This was a deliberate choice made during this
   milestone (bordered pills read more clearly as 3 distinct facts, one of
   which — cap tier — is explicitly a placeholder and needed a visually
   distinct dashed treatment), not an oversight, but it's still a visible
   style mismatch worth a second look if the owner wants an exact match.

### B. Intentional deviations — do not "fix" these without asking

1. **The coverage banner** (`siCoverageBanner`, "Market data · CURRENT / SI
   coverage · READY ...") does not exist in the reference at all. It is
   real, existing ATHENA-specific data-freshness honesty from SI-P2A/P2B,
   not a reference-mock element — removing it to match the reference would
   be a regression, not a fix.
2. **Refresh/Clear buttons and the GET-vs-Analyze helper text** are real
   ATHENA request-lifecycle affordances (added earlier this same session,
   independent of the reference-matching plan) that the generic reference
   mock has no equivalent for. Keep them.
3. **The reference's global left sidebar** (Home/Markets/Watchlist/
   Research/Portfolio/Tools/Settings) belongs to a different app, not
   ATHENA's own app-shell nav — this was an explicit non-goal in the
   original approved plan and remains out of scope.
4. **The "LIVE ENGINE ACTIVE" / "API UP · MANUAL CYCLES" pill difference**
   is shared app-shell chrome (`03-app-shell.js`), not owned by this SI-
   scoped milestone.

## Remaining work

Owner/Chief Architect visual and source review, **plus a decision on which
of the "Real gaps worth closing" above (if any) should become a follow-up
SI-P2B.2 milestone** — none of them were in the original approved plan's
section-by-section scope, so none were treated as blocking this milestone's
completion, but they are the reason the live page still reads sparser than
the reference. Not yet marked frozen.
