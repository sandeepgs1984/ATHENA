# My Portfolio Dashboard Revamp

**Status: Owner/Chief Architect approved 2026-09-11 — MP-RV1 approved and
closed; MP-RV2 implemented, ready for review.**
Authorized after the 14-item Next-Level UX roadmap closed with MP-NX6C
(`docs/design/MY-PORTFOLIO-NEXT-LEVEL-UX-ROADMAP.md`). This is a **new**,
separately-authorized track — not a reopening of Portfolio Intelligence V2
or the Next-Level UX roadmap. Every milestone here is presentation-only:
no methodology, DTO, schema, interpretation-version, sync, privacy-contract,
or scoring change. If a milestone is found to need any of those, it stops
and an ADR/owner-approval path is followed instead of proceeding silently.

## 1. Origin

### MP-RV2 scroll bleed correction (2026-09-12)

The owner reported the bleed remained after the earlier stacking and
scroll-landing corrections. A synthetic browser fixture loading the real
shell and Portfolio styles reproduced a row visibly ABOVE the opaque header
after wheel scrolling: the scrollport starts at y=72, while the sticky header
remained at y=104. The 32px scroll-container top padding was an uncovered
paint strip. Sampling points only inside the header missed this defect;
no GPU race is needed to explain this reproduced case.

The active Portfolio tab now sets its parent viewport's top padding to zero
and places the same initial 32px padding on the workstation content. That
space scrolls away, letting the sticky header meet the viewport edge. Square
header corners close edge cutouts. Speculative transform/backface promotion
was removed. The existing section landing measurement and tab-switch refresh
remain unchanged. Other tabs retain their original viewport padding.

Browser wheel-scroll screenshots verified the formerly exposed row is hidden
and scrolling back to the top preserves initial spacing without a curtain
covering the overview. Verification used synthetic data and the real styles;
the production page required authentication and native Chrome automation was
unavailable. Owner confirmation on production remains pending. Assets are
cache-busted at all three levels to 9.224.0. MP-RV2 remains in review; no
subsequent milestone is started.

Regression result: full suite 4017 passed, 1 pre-existing macOS launcher
failure. Ruff retains three existing E501 assertions in the hosting test.
The new hosting regression passed as part of the full suite. Visual checks
covered 1280px and 390px widths, wheel scrolling, and returning to the top.

The owner reviewed five real screenshots of the live My Portfolio page
(header/summary/triage; risk/heatmap; holdings table top; holdings table
bottom + upload/imports) and asked for a "world class best user experience"
redesign. A clickable prototype was built and published as a Claude Design
canvas (`https://claude.ai/code/artifact/2db01151-023d-40ab-a01d-a83c96922073`)
to explore direction before touching production code, per the design skill's
own workflow. The owner reviewed it and approved integrating it into the
real dashboard, "section by section with proper testing and verification as
ATHENA's process."

**Correction (2026-09-11, after MP-RV1's first pass shipped): the owner
requires a pixel-accurate match to the prototype's visual design and
interaction behavior for every milestone in this track, not a
"direction reference" the AI may simplify or substitute at its own
discretion.** The first MP-RV1 pass shipped a lighter-weight
scroll-and-highlight shortcut instead of actually relocating/toggling the
upload panel the way the prototype does — the owner rejected that as not
matching the prototype and it was corrected in place (see the
`MP-RV1` row in the milestone table, and its correction entry in
`IMPLEMENTATION_SUMMARY.md`). Going forward, "pixel by pixel" governs:
match the prototype's layout, spacing, states, and interactions exactly,
expressed through ATHENA's own real design tokens/components (never the
prototype's raw placeholder colors where a real token exists), and never
substitute a smaller-diff alternative without asking first.

Before scoping real milestones, the current production code
(`src/athena/api/static/index.html`, `js/08b-my-portfolio.js`,
`css/05b-my-portfolio.css`) was re-audited line-by-line. Several problems
the original screenshot critique named turned out to be **already fixed**
by MP-NX1/MP-NX2/MP-NX6C (Smart Filters already collapsed behind a
"Filters" disclosure; Risk Concentration panel already collapsible and
collapsed by default). Proposing those again would duplicate shipped work,
so they are dropped. What follows is the verified, real gap list — the
actual scope of this track.

## 2. Verified current-state findings (2026-09-11 code audit)

| # | Area | Verified finding |
|---|---|---|
| 1 | Upload entry point | "Choose Holdings File" lives in a card titled "Update Holdings" inside `.my-portfolio-secondary-grid`, one full scroll below the holdings table — not co-located with the header command-center actions (Export / Privacy / Sync / Reset). `index.html:958-1021` |
| 2 | In-page navigation | No sticky/jump-to section nav exists anywhere on the page. The only navigation is the app-wide sidebar tab switcher. All `position: sticky` CSS in the file is scoped to the holdings-table header/first-columns only. |
| 3 | Morning Triage tiles | Already restacked by MP-NX6C (four live attention chips, Queue count, Start review in header, Filters disclosure) — no further IA change needed. No caption exists stating the four triage categories can overlap on one holding; this is genuinely missing. `index.html:596-714` |
| 4 | Per-row badges | A single Symbol cell can stack up to four independently-rendered badge elements: pin badge, note badge, queue-reason chips, and **one `.my-portfolio-change-badge` per distinct change type** (Status/Daily Review/Action/Setup/Trend/P&L-move/remap) — genuinely un-collapsed, confirmed via `myPortfolioChangeBadgeChips()`, `js:1292-1299`. |
| 5 | Filter chips | Already collapsed behind "Filters" since MP-NX6C. **Not a gap — dropped from scope.** |
| 6 | Copy/language | Three real instances of internal-process phrasing leaking into owner-facing text: `"Counts not invented:"` (`index.html:708`, plus repeated in three tooltip titles), `"Server-owned holding math"` (`index.html:569`), `"Download server-owned My Portfolio data."` (`index.html:493`). These are true statements but read as engineering commentary, not product copy. |
| 7 | Heatmap contrast | Tile background tones (`tone-positive`/`tone-negative`/`tone-danger`/etc.) are hardcoded `rgba(...)` literals, not the existing `--tone-good-text`/`--tone-warn-text`/`--tone-bad-text` design tokens (confirmed zero consumers of those three tokens anywhere in `05b-my-portfolio.css`). The real contrast risk is the tile's secondary label span, hardcoded to `var(--text-muted)` (mid-gray) regardless of tile tone — muted-gray-on-tinted-red/green, not literally "dark red on dark red" as first assumed from the screenshot. |
| 8 | Unavailable-state styling | Already muted via a slate-colored row accent bar and neutral chip styling (`myPortfolioRowStateClass`, `myPortfolioUnavailableChip`). No opacity-dimming gap found. **Not a gap — dropped from scope.** |
| 9 | Risk Concentration panel | Already collapsible, default collapsed, since MP-NX2. **Not a gap — dropped from scope.** |

Findings 1, 2, 4, 6, 7 are the real, remaining gaps. They map to five small,
independently reviewable milestones below.

## 3. Milestones

One milestone in flight at a time, per `CLAUDE.md`. Each stops for
Owner/Chief Architect review before the next starts.

| ID | Scope | Files touched | Risk |
|---|---|---|---|
| **MP-RV1** | Promote "Upload Holdings" to a header button (rightmost, accent-filled, matching the prototype's exact style) that opens/closes the existing Update Holdings card as an inline panel directly under the header, with a smooth JS height-driven expand/collapse animation (no scroll jump) — relocates the real card, does not rebuild it. Full header reorder to match the prototype: Privacy → Export → Sync Portfolio (renamed) → Upload Holdings → Reset (icon-only, last). Zero change to the upload/preview/confirm pipeline's ids or logic. | `index.html` (header reorder + relocated panel + close button), `08b-my-portfolio.js` (open/close state, label rename, animation), `05b-my-portfolio.css` (scoped button styling, expand/collapse animation, single-column secondary grid) | Low — real DOM relocation/reorder and a real default-visibility behavior change, but zero functional-pipeline logic touched; covered by DOM-order tests |
| **MP-RV2** | Add a lightweight sticky in-page sub-nav (Overview / Triage / Risk & Heatmap / Holdings) above the KPI strip, click-to-scroll to existing section anchors. No new data, no new sections — just navigation over what already exists. | `index.html` (nav markup + 4 anchor ids on existing sections), `08b-my-portfolio.js` (scroll handler + active-section highlighting), `05b-my-portfolio.css` (sticky nav styles) | Low — additive; must verify it doesn't collide with the existing sticky holdings-table thead dock |
| **MP-RV3** | Copy-only pass: replace `"Counts not invented:"`, `"Server-owned holding math"`, and `"Download server-owned My Portfolio data."` with owner-facing phrasing that keeps the same meaning (still never inventing data) without engineering-process language; add one short caption near the Morning Triage tiles noting the four categories can overlap on a holding. | `index.html` only (static text) | Trivial — zero logic change |
| **MP-RV4** | Collapse the up-to-four independent per-row change badges into one compact `"N changes"` indicator per row, with the individual change reasons reachable via a hover title/small popover — no information is dropped, only the default visual footprint. Pin badge and note badge stay separate (they are owner-authored state, not sync-detected change state, and conflating them would blur MP-NX6's "visually and contractually separate from ATHENA evidence" guardrail). | `08b-my-portfolio.js` (`myPortfolioChangeBadgeChips`), `05b-my-portfolio.css` (new indicator style) | Medium — must prove zero information loss with a direct before/after test on a multi-change row |
| **MP-RV5** | Route the heatmap tile's secondary label text through `--tone-good-text`/`--tone-warn-text`/`--tone-bad-text` (matching the tile's own tone) instead of the flat `--text-muted`, for real contrast against tinted backgrounds. Pure CSS token substitution — zero tone-selection logic change. | `05b-my-portfolio.css` only | Low — must screenshot-verify contrast on all five tones (positive/negative/danger/neutral/default) before/after |

## 4. Non-goals (explicit)

- No change to Status / Conviction / Trend / Setup / Daily Review / Next
  Action / Structural Review / EXIT_RISK methodology, or any interpretation
  version bump.
- No schema/DTO change, no new API endpoint, no new persisted field.
- No change to Portfolio Sync orchestration, privacy masking contract,
  export contract, or owner-notes/review-session contracts (MP-NX6/NX6B).
- No re-litigating findings 3/5/8/9 above (already shipped correctly).
- No MP-RV6+ authorized yet — this document covers exactly MP-RV1 through
  MP-RV5; a further milestone needs its own owner authorization, the same
  discipline `MY-PORTFOLIO-NEXT-LEVEL-UX-ROADMAP.md` §"Do not invent MP-NX7"
  already established for the prior track.

## 5. Test & verification discipline per milestone

Per `CLAUDE.md`'s milestone workflow, each of MP-RV1–MP-RV5 individually
goes through:

1. **Design** — scope frozen in this document (this step, done for all five
   up front so the whole arc is visible; implementation still proceeds one
   at a time).
2. **Implement** — the listed files only.
3. **Test** — full `pytest` suite must stay green (these are presentation
   files with no Python coverage of their own, so the suite proves zero
   regression to anything it *does* cover — e.g. no accidental Python-side
   breakage from an unrelated slip); `ruff check` clean; asset cache-buster
   (`index.html`'s `?v=` query strings on the touched JS/CSS files) bumped.
4. **Self-validate** — live-verified in a real browser against a running
   dev/preview server: visual screenshot before/after, console/network
   error check, and a direct interaction test of the changed control
   (click the new button, scroll the new nav, hover the collapsed badge,
   etc.).
5. **Milestone Review Summary** — posted in chat per the standard format
   (scope completed, files touched, tests, risks, commit message) — no git
   action taken unless the owner explicitly asks in that instance.
6. **Stop for Owner/Chief Architect review and approval before MP-RV(n+1)
   starts.**

## 6. Design reference

Direction/interaction reference only, not implemented verbatim (see §1):
clickable prototype — `https://claude.ai/code/artifact/2db01151-023d-40ab-a01d-a83c96922073`.
