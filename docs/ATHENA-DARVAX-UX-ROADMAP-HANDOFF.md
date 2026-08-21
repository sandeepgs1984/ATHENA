# ATHENA & DarvaX UX Roadmap — Agent Handoff

**Snapshot date:** 2026-08-21 — **AUX-6, AUX-7, and AUX-8 all owner-
approved.** The owner-selected priority track (AUX-1a through AUX-8) is
fully approved; nothing is currently in flight.
**Branch observed:** `feature/live-dashboard`  
**Latest commit:** `a53a168` — `feat(dashboard): expose full-cycle validation health`
(none of AUX-7's/AUX-8's own commits are made yet — the AI provides a
commit message per milestone, the owner commits)  
**Test suite at handoff:** **2,181 passing.** Ruff clean on all changed/added
files. Progression: 2,041 -> 2,055 (AUX-4a) -> 2,069 (AUX-4b) -> 2,075
(AUX-5) -> 2,086 (AUX-4c) -> 2,105 (AUX-6, across five owner-caught fix
passes in one day — see below, this is the part worth reading in full
before touching any cross-lane code) -> 2,156 (AUX-7 initial) -> 2,158
(AUX-7's own post-review fix pass, a sixth instance of AUX-6's bug 4 — see
the new gotcha below) -> 2,165 (a further post-approval polish pass on
DarvaX Read's ACTION field and the ATHENA Decision card's timestamp — see
the new section below before touching either) -> 2,178 (AUX-8 initial) ->
2,181 (AUX-8's own fix, wiring DarvaX's existing signal classifier into its
on-demand scan endpoint — see the new section below before touching
`/darvax/api/scan` or `darvaxScanNow` again).

## Message to whichever agent picks this up next

Start with `docs/MILESTONES.md` and the top entry of
`IMPLEMENTATION_SUMMARY.md` per the standard orientation checklist — don't
trust this paragraph's status claims over those two files if they ever
disagree. As of this snapshot: **AUX-1a through AUX-8 are all approved.**
Nothing from the "Unify the two advisory lanes" roadmap category remains
open. Check whether the owner has named a next roadmap item before
starting anything — the "Not yet scheduled" candidates in section 5 below
are real options, not a committed plan. If a further bug surfaces, treat
it the way every bug in this track (AUX-6, AUX-7, and AUX-8 alike) was
treated: root-cause on the actual code (see the testing-methodology lesson
below), fix, add a non-vacuous regression test, re-verify live, update the
docs' bug account — don't just patch and move on silently.

**Before you write a single line of cross-lane (ATHENA <-> DarvaX) UI
code, read the AUX-6 postmortem immediately below in full.** It cost five
separate owner-caught bugs in one day to learn what it now takes two
minutes to read, and every one of the five bugs is exactly the kind of
mistake that's easy to repeat if you reason from first principles instead
of from what's already been learned here.

### AUX-6 postmortem: five bugs, one small feature, all owner-caught

AUX-6 ("See the other view" — a quiet link between a symbol's ATHENA
Decision Brief and its DarvaX read, and vice versa) sounds like it should
be a one-line `<a href>` in each direction. It was not. Every one of the
following was caught by the owner testing on their own real system, not by
this session's own scratch-server verification — a pattern worth noticing
on its own (see the testing-methodology lesson at the end).

1. **ADR-010 Amendment 1 forbids the ATHENA -> DarvaX half from living in
   any ATHENA asset, full stop, even in a comment.** The existing,
   test-enforced rule ("ATHENA's own dashboard assets may never reference
   DarvaX by name anywhere but one script tag") isn't a guideline — the
   first implementation attempt put the link logic in
   `13-decision-brief-core.js` and the full test suite
   (`test_dx4_surface.py`, `test_dx4b_tab.py`) caught it immediately, before
   the owner ever saw it. **The fix, not a workaround**: DarvaX's own
   `tab.js` (already the one file responsible for DOM-injecting things into
   ATHENA's page, per DX-4b) watches `#decision-brief-title`'s `title`
   attribute via `MutationObserver` and injects the link itself when
   DarvaX has a signal for that instrument. This extends Amendment 1's
   already-accepted pattern rather than creating a new exception — no ADR
   needed. **The takeaway that generalizes**: DarvaX-owned files may
   reference ATHENA freely (one-way isolation, by design); ATHENA-owned
   files may never reference DarvaX, ever, in code or comments. If a future
   cross-lane idea needs ATHENA's own assets to know DarvaX exists, that is
   a stop-and-ask architectural question, not an implementation detail.

2. **`target="_blank"` broke authentication, and the first fix attempt
   didn't actually fix it.** Both links originally opened in a new tab,
   under the mistaken belief that a new tab was needed to avoid the DarvaX
   nav tab's iframe going stale (it wasn't — neither link ever touches that
   iframe). A new tab has no guaranteed way to inherit `sessionStorage`
   (where the ATHENA auth token lives), so every click landed on a login
   screen. Attempt 1 dropped `rel="noopener"` alone, theorizing that would
   let the new tab inherit the opener's storage. It looked correct in this
   session's own scratch testing. **The owner's real system proved it
   still broken** — because every scratch server this session used
   `ATHENA_SINGLE_USER=true`, which disables the auth check entirely and
   cannot exercise this class of bug at all.

3. **The actual auth fix broke a different, real case on the very next
   screenshot.** Attempt 2 dropped `target` entirely (same-tab navigation)
   — this genuinely fixed authentication, since same-tab navigation never
   creates a new browsing context, so there's nothing to inherit. But
   viewed through ATHENA's own embedded "DarvaX" nav tab (an iframe), an
   untargeted link only navigates *that iframe* — so the DarvaX-side
   "ATHENA ↗" chip opened a second, nested ATHENA dashboard rendered
   inside the small DarvaX pane instead of navigating the real page.
   **Final fix**: `target="_top"` on the DarvaX -> ATHENA link only —
   always navigates the outermost window of the *same tab* (still no new
   browsing context, so auth stays fine) and is a harmless no-op when the
   page isn't embedded. The ATHENA -> DarvaX link (injected by `tab.js`)
   never needed this: `tab.js` only ever runs in ATHENA's own top-level
   page and is never itself nested, so it stays untargeted.
   `darvax.js`'s own pre-existing top comment already documented the
   sessionStorage fragility that started all of this — read it before
   reaching for any `target` value on a future cross-lane link, and
   remember DarvaX can always be viewed either standalone or embedded.

4. **Fixing the target didn't fix the link's destination.** After
   `target="_top"` stopped the nesting, the ATHENA -> DarvaX link still
   pointed straight at DarvaX's *standalone* `/darvax/...` page. Clicking
   it correctly stayed in one tab, but replaced ATHENA's entire dashboard —
   sidebar included — with DarvaX's bare page, which has none of ATHENA's
   chrome. Caught by the owner from a screenshot: "sidebar of tabs is
   missing." **Fix**: the link now points at `tab.js`'s own `ROUTE`
   (`/dashboard/darvax?symbol=&mode=`) instead of `/darvax/` directly, and
   `build()` reads those same params back out of the URL and forwards them
   into the embedded iframe's `src`, so the embedded view opens
   pre-scoped rather than unfiltered.

5. **What looked like a possible tooling artifact was a genuine race
   condition, and treating it as "maybe just the tool" cost a full extra
   round trip with the owner.** After fix 4, this session's own scratch
   testing couldn't confirm whether the embedded pane ended up *visually*
   active — it kept showing Overview. The first writeup here guessed this
   might be a quirk of the Browser-pane testing tool (which had already
   shown one genuinely tool-specific quirk earlier: `target="_blank"`
   navigating the same simulated tab instead of opening a real new one).
   The owner re-tested on their real Chrome and proved it was a real bug.
   **Root-caused by instrumenting the actual code, not by guessing
   further**: temporarily patched `panel.classList.remove` and the
   `className` setter to log a stack trace on every mutation, then loaded
   a real deep link. The trace pointed straight at ATHENA's own
   `switchTab("overview")`, called via `initializeRoute` from
   `bootstrapSession`. **The root cause**: `tab.js`'s own governing comment
   claims ATHENA's `navItems`/`tabPanes` are a stale snapshot "invisible"
   to a tab injected after page load — but that's only true if the
   snapshot is captured *before* the tab exists. ATHENA's own bootstrap
   captures those NodeLists (and runs its own routing) only *after* an
   async `/api/v1/auth/status` fetch resolves, which happens *after*
   `tab.js`'s synchronous `build()`/`activate()` has already run and
   injected the pane — so by the time `switchTab` finally captures its
   NodeLists, the pane already exists and gets swept in, then immediately
   deactivated since "darvax" isn't one of ATHENA's own tab ids. **Fix**:
   no fixed delay can reliably win a race against a network fetch whose
   timing this file can't know, so a `MutationObserver` now watches for
   exactly this clobbering after a deep-link activation and reasserts
   activation once, then disconnects — both on success and after a
   5-second safety timeout, so it can never fight a real, later,
   deliberate tab switch. Verified live across multiple fresh loads
   (including a check at +800ms) and confirmed a genuine subsequent click
   to a different tab still works normally afterward.

**Two lessons that generalize beyond this one milestone:**

- **`ATHENA_SINGLE_USER=true` is fine for functional/data checks, but it
  cannot prove an auth-carryover fix works.** That needs a real
  authenticated run — for a live dashboard, that means the owner's own
  system. If you're verifying anything involving `sessionStorage`, tokens,
  or cross-page/cross-tab navigation, say so explicitly rather than
  reporting scratch-server success as if it closes the loop.
- **When a live-testing tool shows behavior you can't explain, instrument
  the actual code with a stack-trace-capturing patch before concluding
  it's the tool's fault.** Bug 5's "maybe a tooling artifact" guess was
  reasonable given bug 2's genuine tool quirk, but it was wrong, and
  saying so cost a full extra round trip with the owner that a 10-minute
  `classList.remove` patch would have skipped entirely.

Full technical detail for all five (exact diffs, exact stack traces, exact
test names) lives in `IMPLEMENTATION_SUMMARY.md`'s AUX-6 entry — read it
before modifying `tab.js`, `darvax.js`, or any ATHENA asset that might
touch DarvaX.

### AUX-7 ("Symbol 360"): the architectural question this doc used to leave open, now resolved

Section 5 of an earlier version of this document flagged "where does a
page needing both lanes' data live" as a stop-and-ask question rather than
a call to make unilaterally. It got resolved by direct application of the
AUX-6 postmortem's own asymmetry, once the owner said to just finish the
page: **DarvaX may reference ATHENA freely; ATHENA may never reference
DarvaX.** A page needing both lanes' data therefore has exactly one legal
home — DarvaX-owned, at `/darvax/symbol360` — never an ATHENA route. If a
future cross-lane page ever seems to need the opposite (ATHENA fetching
DarvaX data), that is still the stop-and-ask case; this one wasn't, because
the asymmetry already permits it in this direction.

The other question this doc's earlier version raised — "check whether
saved-symbol status and journal history are already exposed via an
endpoint before assuming new backend work is needed" — resolved cleanly to
**no new backend endpoints at all**. Everything the page needs was already
live: `GET /api/v1/decisions?instrument_id=X&page_size=N` (instrument
filter, sorted newest-first by default — `page_size=1` for the latest
decision, `page_size=10` for history) plus the existing per-decision
`/journal`/`/outcome` endpoints (both `200` with `data: null` when nothing
recorded, never `404`) for ATHENA's half; the existing bulk
`GET /darvax/api/screen/latest?limit=5000` filtered client-side (same
convention `darvax.js`'s own `screenRowFor()` already used), falling back
to the existing `GET /darvax/api/signals/{instrument_id}` when no current
sweep row exists, for DarvaX's half; and the existing
`GET`/`POST`/`DELETE /api/v1/saved-symbols` for the save toggle. Worth
re-reading before assuming a "Big bet"-tagged roadmap item automatically
needs new domain computation — this one didn't, once the actual API
surface was checked rather than assumed.

One new gotcha for the "five gotchas" list above, discovered while wiring
the two entry points: when two independently-injected pieces of UI can
both attach near the same DOM anchor (here, `tab.js`'s synchronous
`showSymbol360Link` and its existing async `checkCrossLink`, both anchored
off `#decision-brief-meta-row`), insertion order is nondeterministic unless
one explicitly anchors after the other. Fixed by having the async one
insert after the synchronous one's element when present
(`var anchor = symbol360El || metaRow`) — a small thing, but exactly the
kind of ordering bug that's invisible in isolated testing of either piece
alone and only shows up once both are on the page together.

**A sixth instance of bug 4 happened anyway, in this very milestone, the
same day.** Both entry points above were first built linking straight at
`/darvax/symbol360?symbol=...` — precisely the "direct link to the bare
standalone page instead of `tab.js`'s own `ROUTE`" mistake bug 4 above
already documents in detail, made again despite that exact postmortem
being read and cited while designing these two links. The owner's
screenshots showed ATHENA's sidebar gone entirely on both links. **The
generalizable lesson, worth internalizing before it costs a seventh
repeat**: reading a postmortem and re-deriving its architectural
conclusion (where should this page live) is not the same as re-running its
concrete checklist against the new code being written (does *this specific
link* stay inside ATHENA's chrome). The fix itself was small — both links
now go through `ROUTE + "?symbol=...&view=symbol360"`, and `build()`'s
existing `?symbol=`/`?mode=` iframe-src forwarding gained a third branch
for `?view=symbol360` pointing the iframe at `/darvax/symbol360` instead of
the main screener — but the mistake itself cost a full owner round trip
that a five-second re-read of bug 4 above, applied deliberately rather than
just cited, would have caught before the owner ever saw it. Full detail
(exact diff, exact test names, live-verification transcript) in
`IMPLEMENTATION_SUMMARY.md`'s AUX-7 entry, under "Post-review fix pass."

**Post-approval: DarvaX Read's ACTION field, three small lessons in one
review.** After the owner approved the milestone, live review of a real
row surfaced a genuine gap and then a genuine overcorrection, both worth
knowing before touching this field again:

1. **A pre-existing humanization map, missed.** Symbol 360's DarvaX card
   printed `row.action` raw (`ENTER_ON_RETEST`) instead of reusing
   `darvax.js`'s own `ACTION_LABEL` map, which every other DarvaX view
   (Advisor, Table) had already been using since well before AUX-7. Lesson:
   before rendering any DarvaX field this page duplicates logic for, check
   whether an existing humanization/formatting convention already exists
   elsewhere in `darvax.js` and reuse it rather than rendering the raw
   value and assuming that's fine because "it's just DarvaX-internal data."
2. **A "clarifying" addition that made things worse, caught by live
   review, not by a test.** The first fix also bracketed the row's trigger
   price next to the label (e.g. "Buy on dip (₹140.46)"), reasoning this
   made the action self-contained. It shipped, was tested (source-level
   guards passed), and only reading the actual rendered page revealed it
   duplicated the very next row ("Buy above ₹140.46"), reading as confusing
   repetition rather than added clarity. Reverted everywhere it had been
   added (`symbol360.js` and, for consistency, `darvax.js`'s
   `actionChip`/`actionCell`, both restored to their untouched original
   form). Lesson: a test proving a value renders correctly cannot catch
   that the value is *redundant next to another value already on screen* —
   that only shows up by looking at the actual rendered card as a whole,
   not at one field's test in isolation.
3. **The label itself was actually misleading, once questioned.** "Buy on
   dip" implies buying at a lower price; the actual mechanic (persisted in
   `action_reason_plain`) is a pullback-and-retest of an already-broken-out
   level, with the real entry trigger identical to a plain `ENTER` — buy
   *above* a price, never at a dip. Renamed app-wide to "Buy on retest" per
   the owner's explicit choice among offered options, with a `title`
   tooltip on both `actionChip` and Symbol 360's own Action row reusing the
   row's own `action_reason_plain` (never a newly written sentence) so the
   concrete retest level is one hover away. Lesson: a label copied verbatim
   from an existing convention can still be wrong on its own terms — reusing
   `ACTION_LABEL` fixed the *raw-code* problem but not this deeper
   *wording* problem, and only the owner asking "how much dip?" surfaced it.

A second, independent fix in the same pass: the ATHENA Decision card's "As
of" line printed a raw ISO timestamp instead of going through ATHENA's own
established `formatDecisionTime` convention (`05-utils.js`) — duplicated
into `symbol360.js` per this file's own no-cross-import rule. Full detail
in `IMPLEMENTATION_SUMMARY.md`'s AUX-7 entry, under "Post-approval polish
pass."

### AUX-8 ("Scan & Validate"): reusing an on-demand endpoint doesn't mean the result matches a passive read

Right after approving AUX-7, the owner asked for a natural next step: enter
a symbol and get both engines' validation "after scanning the symbol
properly" — not just a read of whatever each already happens to have
persisted. Design confirmed with the owner up front (a genuine fork worth
asking about, not deciding alone): **two separate actions, not one** —
"Look up" stays free/instant, "Scan & Validate" is a second, explicit
button shown only once a symbol is loaded, since ATHENA's half makes a
real Kite ingest call and both halves persist new data.

Both halves reuse existing, already-shipped pipelines: ATHENA's
candidate-upsert-then-validate sequence (`09-market-intelligence.js`'s
`validateSymbolsNow`) and DarvaX's per-instrument `POST /darvax/api/scan`.
Zero new routes going in — pure frontend composition, matching AUX-7's own
framing exactly.

**Then the owner compared two screenshots of the same symbol and asked
"shouldn't this be the same as Look up?" — and they were right.** DarvaX's
`/scan` endpoint was deliberately built to skip classification (its own
docstring says so) — it produces a raw signal (`SIGNAL`/`RULE`), not a
sweep's tier/action-classified `ScreenResult`
(`TIER`/`ACTION`/`BUY ABOVE`/`STOP LOSS`). Reusing an existing endpoint
because it does "the same kind of thing" isn't enough — it has to produce
comparable *output*, not just live in the same conceptual space, or two
buttons on the same page for the same symbol will visibly disagree. **The
generalizable lesson**: before wiring an existing endpoint into a new UI
path, check what its response actually contains against what a sibling
path already shows, not just whether the endpoint name matches the intent.

The fix was clean specifically because the classification already existed
as a separate, pure, already-tested function (`screen_signal`) that a real
sweep also calls — wiring it into `/scan`'s handler too, as a new additive
`screened` field, needed no new methodology and no schema change. Full
technical detail (exact diff, exact test names, live-verification
transcript, and why the fix is architecturally safe — no effect on
DarvaX's own existing "Scan symbols" feature) is in
`IMPLEMENTATION_SUMMARY.md`'s AUX-8 entry.

**One more thing worth internalizing before extending "Scan symbols"
itself**: that button on DarvaX's main screener page has the exact same
underlying gap this fix solved for Symbol 360 (its `/scan` call now
returns a classified `screened` result too), but the button's own
frontend code (`darvax.js`'s `scan()`) doesn't read it — it only shows a
count and reloads the last sweep. Flagged as a suggested improvement in
the AUX-8 implementation entry, not fixed here: out of this milestone's
scope, but a real, ready-made follow-up if the owner wants it.

### Everything else approved before AUX-6

AUX-1a, AUX-1b, AUX-2, AUX-3, DX-12b, AUX-4a, AUX-4b, AUX-5, and AUX-4c are
all approved — AUX-4a/4b each independently confirmed by the owner on their
own real, live system (129 real near-misses in a real `athena brief` run;
35 in a real DarvaX sweep, spot-checked by hand). AUX-5 rolled up journal +
realized-outcome history into a new 3-card "My track record" row on the
Overview tab. AUX-4c surfaced AUX-4a's and AUX-4b's near-miss digests by
reading each already-persisted file directly (mirroring
`OpsService.list_backups`'s glob-plus-defensive-parse convention); the
owner's live review asked for the term itself to be self-explanatory, so
both panels carry a plain-language explainer — see
IMPLEMENTATION_SUMMARY.md's AUX-4c entry for the exact wording and the
"Composite score" naming collision that refinement pass caught (an existing
UX-8 regression guard; fixed with the app's established "Score" label).

**One flagged, not-yet-fixed risk, unrelated to AUX-6**:
`get_decisions_service`'s dependency hardcodes `config_dir` to the real
repo root regardless of `ATHENA_CONFIG_DIR`, discovered during AUX-4c's
live verification (read-only, harmless, but will bite any future
config-reading `DecisionsService` method's scratch-isolated testing) — a
background task was spawned for it (`task_57b20ddd`, title "Fix
get_decisions_service config_dir wiring"); check whether it's still
pending before assuming it needs re-flagging.

DX-12b reuses DX-12a's persisted `ema_50`/`ema_100` and its existing
`trendStateFor` classification (no backend/schema change) to render an
omit-when-absent trend badge beside the action chip on Advisor buy tickets,
held-position tickets, and the Levels ladder header. The badge lives in each
card's header row only — it does not touch `levelChart()` or the price
ladder, deliberately avoiding the label-collision class of bug that
redesigned the Levels view once already. See `IMPLEMENTATION_SUMMARY.md`'s
DX-12b entry for full detail.

AUX-3 is owner-approved as of 2026-08-20. It adds the nullable
`analysis.confidence_level` field to the Decisions read model and renders
`Conf High`, `Conf Med`, `Conf Low`, or `Conf -` on each decision row. The only
authority is the canonical persisted `DecisionReport` confidence assessment.
The authenticated dashboard was visually checked for value agreement,
clipping, and row stability.

The tooltip states that ATHENA confidence reflects evidence reliability, not
expected profit. The band is informational only: it does not change sorting,
filtering, Decision classification, TradePlan authorization, or any analytical
contract. A per-request run cache loads each pipeline detail once even when
many list rows share the same run.

On 2026-08-19 the owner delegated prioritisation and began approving a
delivery sequence one milestone at a time, since grown to nine (AUX-1a
through AUX-7, with several splits along the way — AUX-1 -> 1a/1b, AUX-4 ->
4a/4b/4c). The selected sequence is tracked in
`docs/design/ATHENA-DARVAX-UX-ROADMAP.md` and `docs/MILESTONES.md`; the
other roadmap ideas remain unscheduled until the owner picks the next one.

This document is a continuity aid, not the authority on project status. Before
touching anything, read `ATHENA_BRIEFING.md` in full, then verify
`docs/MILESTONES.md`, the newest entry in `IMPLEMENTATION_SUMMARY.md`, and the
current `git log`/`git status`. Those sources override this snapshot if they
disagree with it.

---

## 1. What you're picking up

The owner asked for "best trading experience improvements... to make advisory
dashboard world class and best user experience, these improvements can be
anything." The response was a code survey of both surfaces (ATHENA's own
dashboard and the DarvaX satellite module) to find real gaps rather than
reproposing what already exists, followed by 29 concrete, scoped ideas.

**Read in this order:**

1. `ATHENA_BRIEFING.md` — mandatory, every session, before anything else.
2. `CLAUDE.md` — the process rules below are a summary; that file is authoritative.
3. `docs/design/ATHENA-DARVAX-UX-ROADMAP.md` — the 29 ideas themselves, each
   tagged by surface (ATHENA / DarvaX / both) and effort (quick win / medium /
   big bet), with an "Already there" note where the idea extends existing
   infrastructure rather than building from zero.
4. `docs/ATHENA-TECHNICAL-ARCHITECTURE.md` — how the codebase is actually
   built (backend architecture, the real module map, the frontend's
   server-side JS assembly, security, testing). Read the relevant sections
   before touching a module you haven't worked in.

**AUX-1a through AUX-8 are all approved** — see `IMPLEMENTATION_SUMMARY.md`'s
entry for each (newest first; AUX-6's, AUX-7's, and AUX-8's entries are the
longest and most important to read given the postmortems above). AUX-4c (surfacing
AUX-4a/4b's near-miss digests in the dashboard UI) is also done — both are
file-only digests now surfaced with a plain-language explainer on each
dashboard.

---

## 2. Non-negotiable invariants

These hold regardless of which roadmap item you implement. Violating any of
them is a stop-and-ask situation, not a judgment call:

- **No order-placement code, anywhere, ever.** Not a flag, not a "future"
  stub. Several roadmap ideas (alerts, one-click copy of levels) sit right up
  against this line — they end at *telling* the owner something, never at
  acting on their behalf. Grep for order-placement patterns before trusting a
  claim that a change doesn't introduce any (see `ATHENA-TECHNICAL-ARCHITECTURE.md`
  §3.4 for the exact grep commands used to verify this holds today).
- **Explainability-as-data (ADR-005).** Every value a UI shows must be
  computed and persisted by the engine that produced it. A UI change must
  never re-derive a rationale, a classification, or a "why" in the browser —
  render what's already there, or extend the engine to persist a new field
  and render that.
- **No invented methodology.** DarvaX's DAR-CARD classification (`tier`,
  `action`) must never be influenced by a UX addition — trend context,
  liquidity, filters are all informational/filterable dimensions layered on
  top, never folded into the classification itself. If a roadmap item would
  require inventing a rule the source material doesn't state, stop and ask
  rather than filling the gap yourself.
- **DarvaX keeps its own identity.** `EXPERIMENTAL · UNVALIDATED` badge,
  amber palette distinct from ATHENA's own surface, own database
  (`db/darvax.db`), own schema version — even ideas that unify the two
  surfaces (cross-linking, a shared theme) must preserve this distinction
  rather than blend the two into one visual identity.
- **Single-user, local-only.** No hosted push notification service, no
  multi-user auth model, no cloud dependency — alerting ideas route through
  the existing webhook/file notifier infrastructure (`src/athena/notifications/`),
  not a new external service.

---

## 3. Mandatory workflow — do not skip steps

Per `CLAUDE.md`: **Design → Implement → Test → Self-validate → Milestone
Review Summary → owner approval → next milestone.** Never auto-continue past
an approval gate, and split a milestone before implementing if it's too large
for one sitting (three UI surfaces plus a schema change was judged too large
in this same track — see the DX-12a/DX-12b split in `IMPLEMENTATION_SUMMARY.md`
for the precedent).

**Design step, concretely:**
- Read the actual code the idea touches before proposing an approach. Several
  roadmap ideas explicitly cite what already exists (e.g. "reuses the
  existing webhook/file notifier infrastructure") — verify that citation is
  still accurate before building on it; code moves.
- If the idea is ambiguous about a UX detail (wording, placement, whether it
  gates or only informs), form a specific recommendation and ask the owner
  to confirm rather than silently deciding. Two clarifying questions before
  DX-12a's implementation (informational-vs-gating, which surfaces) is the
  pattern to follow.
- State the design plainly before writing code, and wait if the change is
  non-trivial.

**Git:** the AI never runs git actions (add/commit/push/branch/etc.) unless
the owner explicitly asks in that specific instance. Provide a consolidated
commit message instead, format `<type>(<scope>): <summary>` (≤72 chars,
imperative) + a body of `-` bullets, each stating WHAT and WHY. Types: `docs`,
`feat`, `fix`, `config`, `test`, `refactor`, `chore`.

**Before marking any milestone done, verify all of:** full test suite passes
(`python3 -m pytest -q` from repo root — do not trust a partial run), the
frozen architecture and contracts are unchanged, replayability and determinism
hold, no ADR is silently required, and `IMPLEMENTATION_SUMMARY.md` /
`docs/MILESTONES.md` are updated in the same change set.

---

## 4. Surface-specific gotchas, paid for the hard way this track

These cost real time and real risk earlier in this same UX effort. Read them
before touching the corresponding surface.

### Cross-lane UI (ATHENA <-> DarvaX): six gotchas, one of them repeated once already

Full account at the top of this document ("AUX-6 postmortem" and, right
below it, AUX-7's own "sixth instance of bug 4"). The one-sentence version
of each, for quick reference once you've read the full thing at least
once: (1) ATHENA's own assets may never reference DarvaX by name, anywhere,
even in a comment — inject cross-lane UI from `tab.js` instead. (2) A
cross-lane link must never use `target="_blank"` — cross-tab
`sessionStorage` inheritance isn't reliable, and `ATHENA_SINGLE_USER=true`
scratch testing can't catch this since it disables auth entirely. (3) A
link that might render inside DarvaX's embedded iframe (via ATHENA's own
"DarvaX" nav tab) needs `target="_top"`, or it nests a dashboard inside a
pane instead of navigating the real page. (4) **A link meant to land inside
ATHENA's own chrome must target `tab.js`'s `ROUTE` (`/dashboard/darvax?...`
with whatever `?view=`/`?mode=`/`?symbol=` params `build()` already
understands or needs extending to understand), never `/darvax/...`
directly, or the sidebar disappears — this one was made twice, once in
AUX-6 and, despite having read that postmortem, again in AUX-7 for a new
page (`/darvax/symbol360`). Before adding ANY new href that points into
DarvaX from a cross-lane UI element, grep this file and `darvax.js` for
existing `ROUTE`/`/dashboard/darvax` usages and follow that pattern
precisely — do not construct a fresh direct link to a DarvaX page path,
ever, no matter how good the reason seems in the moment.** (5) A deep link
to that `ROUTE` races against ATHENA's own async auth-bootstrap-then-route
sequence and will lose without a `MutationObserver`-based reassertion —
don't assume a "static NodeList" comment is still accurate without
checking the actual timing. (6) Two independently-injected pieces of UI
anchored near the same DOM element (an async one and a sync one) need an
explicit ordering rule, or their insertion order is nondeterministic.

### DarvaX: never test against the owner's real database

`config/darvax.json`'s `database.path` points at `db/darvax.db` — the
owner's real, accumulating data. **Twice** during this track, a test or an ad
hoc verification run wrote real sweeps into it (once via a test-suite defect,
once via manual verification). Both times it was caught and cleaned up, but
the second incident specifically motivated an autouse hermetic-isolation
fixture (`tests/darvax/conftest.py`) because "remember to point at a scratch
config" is not a safeguard — making it structural is.

**For any manual/browser verification of a DarvaX change**, use a scratch
config and scratch database, never the real ones:

```bash
SC=<your scratch dir>
cp -R config $SC/vcfg
python3 -c "
import json, pathlib
p = pathlib.Path('$SC/vcfg/darvax.json'); d = json.loads(p.read_text())
d['database']['path'] = '$SC/vdb.db'; p.write_text(json.dumps(d, indent=1))
"
PYTHONPATH=src ATHENA_CONFIG_DIR=$SC/vcfg ATHENA_OWNER_PASSWORD_HASH= ATHENA_SINGLE_USER=true \
  python3 -m uvicorn athena.api.app:create_app --factory --port 8100 --host 127.0.0.1
```

`ATHENA_SINGLE_USER=true` with an empty `ATHENA_OWNER_PASSWORD_HASH` is a
supported single-user auth bypass — without it every API call 401s and a
manual check will look like the feature is broken when it isn't. Verify the
owner's real sweep count is unchanged before and after your session
(`sqlite3 file:db/darvax.db?mode=ro`).

### Frontend: bump the asset version on every static edit

`index.html` references `dashboard.js?v=X.Y.Z` / `dashboard.css?v=X.Y.Z`
(ATHENA) and `darvax.css?v=...` / `darvax.js?v=...` (DarvaX, versioned
independently). **The browser caches these aggressively.** Edit a `.js`/`.css`
file and forget the version bump, and your change silently won't appear on
reload — this has happened in this session and reads exactly like a broken
feature until you notice the version string didn't move.

### Frontend: escaped em-dashes, not the literal character

`darvax.js` writes em-dashes as the six-character escape sequence
(backslash, lowercase u, then 2014) inside its JS string literals, rather
than the Unicode em-dash character itself. String-replace tooling that
assumes the Unicode character is present in the source will silently fail to
match. When an edit tool rejects a string you copied verbatim from a file
read, suspect an escape mismatch before assuming the file changed — read the
exact bytes around the target and match them precisely (or slice by index in
a small script) rather than retyping the string from memory.

### Frontend: a duplicate function declaration wins silently

JavaScript's function-declaration hoisting means declaring `function money()`
twice in one file doesn't error — the later declaration silently wins, and
every earlier caller now gets its behavior. This shipped once in this track
(a redefinition of a currency formatter produced doubled "₹₹" symbols
everywhere) and is now guarded by a repo test
(`test_no_function_is_declared_twice` in `tests/darvax/test_dx9a_table_values.py`)
scanning for exactly this. If you add a helper function to `darvax.js` or
`dashboard.js`, grep for the name first.

### Testing: prove a new regression guard actually guards something

A test that passes without the bug present and *also* passes with the bug
reintroduced is worse than no test — it reads as coverage that doesn't exist.
The pattern used throughout this track: after writing a guard, temporarily
reintroduce the exact bug it's meant to catch (via a small script editing the
file, running the single test, checking it fails), then restore the good
version and confirm it passes again. Do this for any test whose whole point
is catching a specific class of mistake (a missing disclosure, a hardcoded
value that should be dynamic, a broken invariant) — not for every test.

### Local browser verification: raw HTML files need their own `<meta>` tags

If you preview a fragment or scratch HTML file directly (not through the
`Artifact` publish path, which wraps content in a proper `<!doctype html>`
shell), it has no `<meta charset="utf-8">` and no
`<meta name="viewport">`. Two symptoms this produces, both false alarms about
the actual content: Unicode punctuation (em-dashes, curly quotes) renders as
mojibake without a charset declaration, and a mobile-width resize silently
renders at a default ~980px desktop-style viewport without a viewport meta
tag, making a page that will render fine once published look broken in local
testing. Wrap a temporary copy with both tags for local verification rather
than concluding the content is broken.

---

## 5. Picking up a specific item

Each idea in `docs/design/ATHENA-DARVAX-UX-ROADMAP.md` names its surface and
effort tier — that document's own "Owner-selected delivery sequence" table
at the top is the authoritative record of what's approved vs. still open;
this section adds context the roadmap doc itself doesn't carry.

**Done, no longer open to pick up**: "Trend badge on Advisor cards" (DX-12b),
"Daily near-miss digest" both sides (AUX-4a/4b), "surface the near-miss
digests in the dashboard UI" (AUX-4c), "My track record panel" (AUX-5),
"See the other view cross-link" (AUX-6, see the postmortem above before
touching anything near it again), "Symbol 360" page (AUX-7, approved — see
its own sections above, including the post-approval ACTION-field lessons,
before touching `symbol360.html`/`symbol360.js` or either entry point
again), "Scan & Validate" on Symbol 360 (AUX-8, approved — see its own
section above, including the `screen_signal` wiring lesson, before
touching `athenaValidateNow`/`darvaxScanNow` or `/darvax/api/scan` again),
the persistent freshness indicators (AUX-1a/1b), the last-successful-cycle
indicator (AUX-2), and the confidence band in the Decisions list (AUX-3).

**The "Unify the two advisory lanes" category is fully worked through.**
The owner-selected priority track (AUX-1a through AUX-8) is fully
approved. Whoever picks this up next should
confirm with the owner what they want to schedule next — the candidates
below are real options from the still-unscheduled roadmap menu, not a
committed plan. DarvaX's own "Scan symbols" feature could reuse AUX-8's new
`screened` field too (see the AUX-8 section above) — a real, ready-made
follow-up if the owner wants it, not yet scheduled.

**Not yet scheduled, but real candidates the owner might pick next**:
"Owner-authored price/level alerts" (Alerts, big bet — the single
idea with the most architectural surface area; needs a rules engine and a
per-cycle evaluation pass, not just a UI change; treat as multiple
milestones from the start). "DarvaX's own realized-performance view"
(Performance & conviction analytics, DarvaX-only, explicitly excluded from
AUX-5's scope) — a pure rollup over `darvax_positions`, similar shape to
AUX-5 but DarvaX-side. Check current row counts in `darvax_positions`
before committing to scope; it was zero as of AUX-5's Design step and may
still be low.

---

## 6. What "done" looks like for any item you pick

Matching the standard this track set: full test suite green, a real browser
verification (not just markup assertions) against realistic data — for
DarvaX, a real sweep on the scratch database described above; for ATHENA,
against whatever local data is available — screenshots or described results
proving the feature works end to end, a Milestone Review Summary, and a
consolidated commit message. Update `docs/MILESTONES.md`'s status column only
after owner approval, and `IMPLEMENTATION_SUMMARY.md` in the same change set
the milestone completes.
