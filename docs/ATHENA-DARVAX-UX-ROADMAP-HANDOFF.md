# ATHENA & DarvaX UX Roadmap — Agent Handoff

**Snapshot date:** 2026-08-21 — **AUX-6 owner-approved, confirmed working on
the owner's own real system.** Nothing is currently in flight; **AUX-7 is
next and has not been started.**
**Branch observed:** `feature/live-dashboard`  
**Latest commit:** `a53a168` — `feat(dashboard): expose full-cycle validation health`
(none of this track's own commits are made yet — the AI provides a
commit message per milestone, the owner commits)  
**Test suite at handoff:** **2,105 passing.** Ruff clean on all changed/added
files. Progression: 2,041 -> 2,055 (AUX-4a) -> 2,069 (AUX-4b) -> 2,075
(AUX-5) -> 2,086 (AUX-4c) -> 2,105 (AUX-6, across five owner-caught fix
passes in one day — see below, this is the part worth reading in full
before touching any cross-lane code).

## Message to whichever agent picks this up next

Start with `docs/MILESTONES.md` and the top entry of
`IMPLEMENTATION_SUMMARY.md` per the standard orientation checklist — don't
trust this paragraph's status claims over those two files if they ever
disagree. As of this snapshot: the owner-selected priority track is
**AUX-1a through AUX-6, all approved.** The next item in the owner's own
sequence is **AUX-7 ("Symbol 360" page)** — a "Big bet"-sized item that has
not been designed yet and will almost certainly need its own split before
implementation, the same way AUX-1 and AUX-4 were split. Do not start
implementing it directly; start at the Design step, per the mandatory
workflow, and expect to come back to the owner with a proposed split before
writing code. Section 5 below has concrete starting notes for it.

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

On 2026-08-19 the owner delegated prioritisation and approved a six-item
delivery sequence. The selected sequence is tracked in
`docs/design/ATHENA-DARVAX-UX-ROADMAP.md` and `docs/MILESTONES.md`; the other
roadmap ideas remain unscheduled.

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

**AUX-1a through AUX-6 are all approved** — see `IMPLEMENTATION_SUMMARY.md`'s
entry for each (newest first; AUX-6's entry is the longest and most
important to read given the postmortem above). **AUX-7 ("Symbol 360" page)
is next, not started, needs its own Design step.** AUX-4c
(surfacing AUX-4a/4b's near-miss digests in the dashboard UI) is also done
— both are file-only digests now surfaced with a plain-language explainer
on each dashboard.

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

### Cross-lane UI (ATHENA <-> DarvaX): five gotchas in one milestone

Full account at the top of this document ("AUX-6 postmortem"). The
one-sentence version of each, for quick reference once you've read the
full thing at least once: (1) ATHENA's own assets may never reference
DarvaX by name, anywhere, even in a comment — inject cross-lane UI from
`tab.js` instead. (2) A cross-lane link must never use `target="_blank"` —
cross-tab `sessionStorage` inheritance isn't reliable, and `ATHENA_SINGLE_USER=true`
scratch testing can't catch this since it disables auth entirely. (3) A
link that might render inside DarvaX's embedded iframe (via ATHENA's own
"DarvaX" nav tab) needs `target="_top"`, or it nests a dashboard inside a
pane instead of navigating the real page. (4) A link meant to land inside
ATHENA's own chrome must target `tab.js`'s `ROUTE`
(`/dashboard/darvax?...`), never `/darvax/` directly, or the sidebar
disappears. (5) A deep link to that `ROUTE` races against ATHENA's own
async auth-bootstrap-then-route sequence and will lose without a
`MutationObserver`-based reassertion — don't assume a "static NodeList"
comment is still accurate without checking the actual timing.

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
touching anything near it again), the persistent freshness indicators
(AUX-1a/1b), the last-successful-cycle indicator (AUX-2), and the
confidence band in the Decisions list (AUX-3).

**AUX-7 — "Symbol 360" page — is next, and is where you should start.**
Roadmap doc's own description: "One search box, one page: ATHENA's
Decision, DarvaX's screen result, saved-symbol status, and journal history
for that instrument, side by side." Tagged "Big bet" effort and "Pure
presentation over data every engine already persists — no new analytical
logic, respects explainability-as-data throughout" (i.e. the roadmap's own
author believed no new domain computation is needed — verify that's still
true before designing, the same way AUX-4a's near-miss framing had to be
corrected once the actual persisted-data shape was checked).

Before proposing a design, at minimum:
- Read what AUX-6 already built and reuse it rather than duplicating: the
  `instrument_id -> decision_id` join `darvax.js`'s `loadAthenaCrossLinks()`
  already does via `GET /api/v1/decisions/latest`, and the DarvaX-signal
  existence check `tab.js`'s `checkCrossLink()` does via
  `GET /darvax/api/signals/{instrument_id}`. A Symbol 360 page needs
  exactly these two lookups, just rendered as a full page instead of a
  quiet chip.
- Decide where this page actually lives, given the ADR-010 asymmetry from
  the postmortem above: since it needs to show BOTH ATHENA and DarvaX data
  together on one page, does it live as a new ATHENA route (meaning DarvaX
  data must be fetched by ATHENA's frontend, which is exactly what
  Amendment 1 forbids for ATHENA-owned assets) — or does it need to live
  as a DarvaX-owned page/route instead (matching the established
  asymmetry: DarvaX may reference ATHENA, not the reverse), or does it need
  a genuinely new, neutral page that itself isn't "owned" by either lane's
  existing asset-isolation rules? **This is exactly the kind of
  architectural question the postmortem above says to stop and ask about
  rather than deciding unilaterally** — surface it to the owner as part of
  the Design step, don't guess.
- Check whether "saved-symbol status" and "journal history" are already
  exposed via an endpoint (search for "saved" and "journal" across
  `src/athena/api/v1/routers/`) before assuming new backend work is needed.
- Given "Big bet" sizing and this session's own precedent of splitting
  oversized milestones (AUX-1, AUX-4), expect this to become 2-3
  sub-milestones (e.g., page shell + ATHENA half; DarvaX half; saved-symbol
  and journal history integration) rather than one — propose the split to
  the owner before implementing any of it.

**Not yet scheduled, but real candidates the owner might pick next if not
AUX-7**: "Owner-authored price/level alerts" (Alerts, big bet — the single
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
