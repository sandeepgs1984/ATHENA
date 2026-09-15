# SI-P2B.1 — Stock 360 Reference-Matched Visual Revamp

**Status:** Reference-gap closure implemented, presentation-only, on asset
`9.275.0`. Owner review pending. SI-P2B's own frozen contract
(`docs/research/SI-P2B-STOCK-360-IMPLEMENTATION.md`)
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
   First fixed with a 2-tier, then a 3-tier vertical stagger assigned purely
   from sorted position — but a fixed tier count keyed off sort order
   assumes sort-order distance tracks pixel distance, which breaks whenever
   real values cluster unevenly (a real case: 5 of 7 levels packed into a
   narrow band with 2 outliers far away still collided even at 3 tiers,
   found and reported by the owner against real data). **Superseded** by
   `siPositionLadderCards`: a runtime pass that measures each card's actual
   rendered width/height after insertion via `getBoundingClientRect()` and
   greedily sweeps left-to-right, placing each card in the first tier whose
   last-placed card clears it by a fixed gap (classic interval-scheduling,
   not a magic-number heuristic) — correct for any distribution or count of
   levels, not just the frozen d1 schema's max of 7. Re-runs on section
   switch (`showSiSection`) and on window resize (a tiering computed at one
   width can collide at another), and is a deliberate no-op when the
   narrow-viewport CSS fallback (`position: static`, item 3 below) is
   active, clearing any stale inline offsets so the two mechanisms never
   fight each other.
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
screenshots) across real data shapes: a tied-value case matching the owner's
own reported ACMESOLAR data, a 7-distinct-level case, mobile width, and — for
item 2's runtime-measurement replacement — the exact 7-level, tightly-
clustered case the owner reported against the 3-tier approach, plus a
desktop→mobile→desktop resize round-trip (confirming the CSS-fallback and
runtime-tiering mechanisms hand off cleanly in both directions) — zero
collisions in every case, dots confirmed exactly on the track.

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

**Closure note (2026-09-14, asset `9.265.0`):** All five gaps in section A
below are now closed. The list is retained as the historical pre-closure
comparison that governed this follow-up; it is no longer remaining work.
The chart is now the first major Stock 360 content, with a truthful three-row
Trend / RSI Momentum / Volume
glance panel. Research Brief / Portfolio / Capability and Price Map / ATHENA
View / DarvaX now form the two reference-ordered three-card rows on wide
screens. The Symbol Intelligence header/footer taglines and asset line are
present, and identity metadata uses plain pipe-separated text while keeping
the unavailable cap tier visibly provisional. The existing chart renderer,
coverage semantics, request controls, sidebar, API, DTO, and methodology were
not changed.

Closure verification used the isolated port-8100 server with a scratch config
and scratch database, plus routed synthetic persisted evidence. JavaScript
geometry assertions passed at 1579px, 1024px, and 390px: no horizontal
overflow, no peer-card or Price Map label collisions, chart before both card
rows, exact ladder-dot anchoring where the track is active, correct responsive
chart-panel placement, borderless identity metadata, and the requested header
and footer copy. The 1024px run initially exposed a real narrow Price Map
collision; the intermediate layout was corrected and the same check passed on
rerun. The required focused/integrated suite finished with **96 passed and the
one pre-existing SI-P2E failure**
(`test_si_p2e_no_decision_and_invalid_symbol_are_distinct`). JavaScript syntax,
CSS brace balance, scoped Ruff, and `git diff --check` passed.

**Post-closure addendum (same day, asset `9.266.0`):** the fixed 3-tier
stagger this closure shipped was still not sufficient — the owner reported
a real Price Map screenshot (7 levels, 5 packed into a narrow band with 2
outliers) showing two cards overlapping. Root cause: a tier assigned purely
from sort order assumes sort-order distance tracks pixel distance, which is
false whenever real values cluster unevenly. Replaced with
`siPositionLadderCards` — a runtime greedy left-to-right sweep over each
card's actual measured width/height (see Defects item 2 above for the full
mechanism) — verified against the owner's exact reported data shape (zero
collisions) plus the previously-verified tied-value, 7-distinct-level,
and mobile cases, plus a desktop→mobile→desktop resize round-trip. Full
suite re-confirmed at 96 passed / the same one pre-existing failure.

**Reference-fidelity addendum (same day, asset `9.267.0`):** direct
side-by-side review of the owner's current desktop captures against the
reference exposed a second class of gaps: section grouping was correct, but
the shell, hero, card density, and internal card geometry still did not read
like the reference. The Symbol Intelligence search controls now join the
desktop header row (and return to the in-flow toolbar below 1181px), identity
now precedes the section navigation, and the hero is materially shorter with
reference-weight identity/price typography and a subdued ATHENA phrase instead
of the bright generic gradient panel. The Research Brief no longer renders a
second nested card; held Portfolio metrics form the reference's 3-by-2 grid;
Capability badges share a row; card titles use title case; the two desktop
card rows use reference-proportioned columns; and ATHENA View/DarvaX/coverage/
footer density was tightened without inventing evidence or removing ATHENA's
required controls. The redundant third ATHENA View evidence button was removed
only when the two primary Decision destinations are already present; the
no-Decision evidence path remains available.

The frozen SI-P2C chart renderer, its 460px plotting surface, window controls,
legend, tooltips, and interaction geometry remain unchanged. Consequently the
full page cannot have the reference mock's exact vertical coordinates: that
mock depicts a roughly 146px sparkline-style chart. This is an intentional
contract boundary, not an unclosed CSS defect. Exact full-page-height parity
would require explicit authorization to reopen SI-P2C; every surrounding
Stock 360 section was aligned without doing so. The mandatory coverage banner,
Refresh/Clear controls, GET/Analyze helper, and ATHENA app shell also remain
intentional deviations documented in section B.

**Owner screenshot-correction addendum (same day, asset `9.268.0`):** six
owner captures exposed state and chrome defects that geometry-only checks did
not: the desktop helper was ellipsized, the sticky navigation's 32px-era mask
no longer matched the workspace's compact 12px inset and overpainted its own
border, unresolved bundles were passed through the valid identity hero, and
empty/no-match states were raw strings. The helper copy is now shorter without
losing GET/Analyze semantics and is never clipped; the sticky mask follows the
actual inset, remains opaque, and preserves its border/corners; initial,
empty-input, invalid-symbol, no-catalog-match, and search-error presentations
are distinct and intentional; invalid identities no longer show fabricated
hero placeholders. Valid identity dates now use `11 Sep 2026` formatting and
the price caption follows `LAST CLOSE · date · MARKET CLOSED`, matching the
reference. Price Map values now have explicit high-contrast typography,
category-tinted borders, a brighter track, and hover/keyboard-focus emphasis;
the measured collision algorithm and every underlying value remain unchanged.
The latest focused/integrated release set passes **98 tests**, with only the
same pre-existing concurrent SI-P2E wording assertion failing. JavaScript
syntax, CSS brace balance, scoped Ruff, and `git diff HEAD --check` pass.

**Integrated-shell addendum (same day, asset `9.269.0`):** the valid-symbol
identity hero and section navigation now read as one continuous framed surface
in normal flow: the hero owns the upper radii, the navigation owns the lower
radii, and a single subtle divider joins them. When the navigation becomes
sticky it restores its own complete rounded border and uses only an opaque
outer shadow to cover the scroll inset; the pseudo-element that could overpaint
the top border is disabled. The chart glance now admits the persisted coherent
SuperTrend direction and optional exact `supertrend_value` alongside Trend,
RSI, and Volume; SMA20/SMA50/completed D1 remain in the adjacent chart legend
and are not duplicated. ATHENA/DarvaX actions now share explicit icon width,
gap, height, line-height, and alignment. The coverage banner is now a quiet
borderless status rail with colored status dots and one top divider rather than
another nested box/pill cluster. Responsive geometry, sticky-border,
SuperTrend-value, and collision checks pass at 1579/1024/390px.

**Borderless-shell correction (same day, asset `9.270.0`):** owner review of
normal and scrolled captures showed that joining the hero and navigation with
a larger rounded outline still read as two nested boxes, while sticky mode's
independent rounded border doubled against the chart edge below. The hero and
navigation now form a flat, continuous header band with no outer perimeter or
corner radius. A subtle internal lower divider preserves hierarchy; sticky
mode uses the same opaque square-edged band plus a soft lower shadow, with no
pseudo-element or border that can collide with chart corners. Automated
geometry at 1579/1024/390px confirms a zero-pixel hero/navigation seam, zero
nav border/radius in normal and sticky states, exact sticky offset, no overflow,
and no card or Price Map collisions.

**Atmospheric-shell correction (same day, asset `9.271.0`):** the next owner
captures showed that removing the outline alone left an opaque square hero
fill and an overly separated sticky strip. The hero is now transparent to the
workspace, the redundant top workspace inset is removed,
and sticky navigation has no divider or perimeter—only a restrained lower
shadow. The chart glance panel is likewise borderless, separated from the plot
by one low-opacity rule, and major Stock 360 card borders/background washes are
reduced so evidence hierarchy comes from spacing and typography rather than a
wall of boxes. A zero-scroll geometry check also exposed stale sticky state:
it initialized against the empty hero and did not recompute after identity
content changed the layout. Identity and viewport resize now resynchronize
that presentation state. No chart internals or evidence changed.

**Sticky-continuity correction (same day, asset `9.272.0`):** normal-flow
navigation remains visually quiet, but the docked state now carries compact,
duplicate symbol context (symbol, completed price, and completed-D1 date) at
desktop width instead of becoming an orphaned tab strip. Intermediate width
keeps only the symbol; phone width omits the duplicate context. The decorative
hero quote loses its residual panel fill, pattern, and divider, so the identity
row blends fully into the workspace. This is presentation-only duplication of
already-rendered evidence; no new value or contract was introduced.

**Surface-unification correction (same day, asset `9.273.0`):** the chart
composition now owns one continuous tonal canvas while the plot stage and
glance rail are transparent children, eliminating the dark plot rectangle
against a different side-panel surface. Normal navigation loses its remaining
bottom rule; docked navigation is distinguished by an elevated translucent
surface and shadow rather than a competing line. Inactive destinations and
their icons receive readable contrast, the active destination remains dominant,
and the bottom coverage/status rail loses its unnecessary top separator.

**Chart-frame closure (same day, asset `9.274.0`):** the continuous tonal
canvas now belongs to the outer chart card itself, while the composition,
plot stage, and glance rail remain transparent. This removes the differently
colored padding moat that still framed the chart in the owner's normal and
scrolled captures. The docked navigation also gains a short borderless lower
fade so it separates from moving chart content without restoring an outline
or creating a second rule against the chart card. This is presentation-only;
the frozen SI-P2C renderer, dimensions, evidence, and interaction behavior are
unchanged.

**Regression-copy correction (same day, asset `9.275.0`):** the toolbar now
describes the untouched DarvaX operation generically as a satellite scan so
ADR-010's source guard continues to identify exactly one DarvaX-owned HTML
injection. The no-Decision surface uses the already-approved “Stock 360
research remains available” wording. Meaning and behavior are unchanged; this
only reconciles visible copy with the frozen ownership and regression checks.

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

Owner/Chief Architect visual and source review of the `9.275.0` closure.
SI-P2B.1 remains **IMPLEMENTED / REVIEW-READY**, not frozen. SI-P2E remains
paused; this follow-up did not implement or start additional SI-P2E work.
