# ATHENA & DarvaX UX Roadmap — Agent Handoff

**Snapshot date:** 2026-08-20 (updated — AUX-4c implemented, awaiting owner review)  
**Branch observed:** `feature/live-dashboard`  
**Latest commit:** `a53a168` — `feat(dashboard): expose full-cycle validation health`
(none of this track's own commits are made yet — the AI provides a
commit message per milestone, the owner commits)  
**Test suite at handoff:** **2,086 passing** (2,041 -> 2,055 for AUX-4a,
-> 2,069 for AUX-4b, -> 2,075 for AUX-5, -> 2,086 for AUX-4c). Ruff clean on
all changed/added files.
**Current working milestone:** **AUX-4c, implemented, awaiting owner
review.** AUX-1a, AUX-1b, AUX-2, AUX-3, DX-12b, AUX-4a, AUX-4b, and AUX-5
are all approved — AUX-4a/4b each independently confirmed by the owner on
their own real, live system (129 real near-misses in a real `athena brief`
run; 35 in a real DarvaX sweep, spot-checked by hand). AUX-5 rolled up
journal + realized-outcome history into a new 3-card "My track record" row
on the Overview tab (Win Rate / Avg Return per Trade / Plan Adherence).
**AUX-4c** surfaces AUX-4a's and AUX-4b's near-miss digests by reading each
already-persisted file directly (mirroring `OpsService.list_backups`'
glob-plus-defensive-parse convention rather than adding new persistence): a
new "Near Misses" card on the ATHENA Overview tab, and a new "Near misses"
zone in DarvaX's Advisor view (independent of the live sweep state — it can
go stale between sweeps by design, same as the digest itself). Verified
live: the DarvaX side against a fully isolated scratch server; the ATHENA
side incidentally read the owner's real `artifacts/briefings/
brief-2026-08-20.json` because `get_decisions_service`'s dependency
hardcodes `config_dir` to the real repo root regardless of
`ATHENA_CONFIG_DIR` — read-only, pre-existing, not introduced by this
milestone, but flagged as a risk for future scratch-isolated verification
work on any config-reading `DecisionsService` method.

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

**DX-12b, AUX-4a, and AUX-4b are all approved** -- see
`IMPLEMENTATION_SUMMARY.md`'s entries for each. **AUX-5 is the current
Design gate.** AUX-4c (surfacing AUX-4a/4b's near-miss digests in the
dashboard UI, currently file-only) is registered but not started, queued
behind AUX-5.

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
effort tier. A few notes on ones that carry extra context worth knowing before
you scope them:

- **"Trend badge on Advisor cards"** (Visual & interaction polish, DarvaX,
  quick win) was **DX-12b** — done, awaiting owner review (2026-08-20). It
  ended up covering the Levels view too, per the owner's own scoping
  instruction, not just Advisor. See `IMPLEMENTATION_SUMMARY.md`'s DX-12b
  entry. This item is no longer open to pick up.
- **"Owner-authored price/level alerts"** (Alerts, big bet) is the single
  idea with the most architectural surface area — it needs a rules engine
  and a per-cycle evaluation pass, not just a UI change. Treat this as
  multiple milestones from the start; don't let it become the oversized
  single milestone this track already had to split once (DX-12).
- **"My track record" panel / DarvaX's realized-performance view**
  (Performance & conviction analytics) are pure rollup views over data that
  is *already fully captured* (`TradeOutcome`, `DecisionJournalEntry` on the
  ATHENA side; `darvax_positions` on the DarvaX side). These are good
  candidates for a first milestone precisely because the hard part — capturing
  the data — is done; confirm this is still true by reading those tables'
  current row counts before committing to scope, since an owner with very
  little accumulated history may get a rollup view with little to show yet.

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
