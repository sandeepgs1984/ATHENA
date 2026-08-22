# ATHENA Explosive Move Radar Handoff

**Snapshot:** 2026-08-21 (EM-1r4 implementation added 2026-08-22)
**Governing boundary:** ADR-012
**Current state:** EM-1r3 owner-approved; EM-1r4 implemented and awaiting owner review

## 1. Current milestone state

| Milestone | State |
|---|---|
| EM-0 | Owner-approved 2026-08-21 |
| EM-1a | Owner-approved 2026-08-21; zero checkpoints accepted |
| EM-1r1 | Owner-approved 2026-08-21 |
| EM-1r2 | Owner-approved 2026-08-21 |
| EM-1r3 | Owner-approved 2026-08-21 |
| EM-1r4 | Implemented, tested, live-verified; awaiting owner review |
| EM-1r5 | Blocked until EM-1r4 owner approval |
| EM-1b | Blocked until EM-1r5 approves a non-empty checkpoint set |

EMR remains isolated research. Nothing completed so far changes ATHENA's UI,
score, confidence, risk, eligibility, Decision, TradePlan, scanner, broker, or
order behavior.

**If you're picking this up because the owner approved EM-1r4 in the
meantime:** flip its row in `docs/MILESTONES.md`,
`docs/design/ATHENA-EXPLOSIVE-MOVE-RADAR-ROADMAP.md`, and
`docs/design/EM-1-RESEARCH-DATA-REMEDIATION-PLAN.md` to Approved, and do
not start EM-1r5 without a fresh, explicit owner instruction to do so (this
handoff's own read order and non-goals apply to EM-1r5 just as strictly as
they did to EM-1r4). If EM-1r4 review turned up a bug, treat it the way
the real calendar-coverage bug found during this milestone's own
verification was treated: root-cause on the actual code, fix, add a
non-vacuous regression test, re-verify against real (copied, never
original) data, update this handoff and `IMPLEMENTATION_SUMMARY.md`.

## 2. Mandatory read order

1. `ATHENA_BRIEFING.md`
2. The Explosive Move Radar section of `docs/MILESTONES.md`
3. ATHENA-002 Sections 2 and 19 and their Definition of Done constraints
4. `docs/adr/ADR-011-canonical-symbol-master-and-universes.md`
5. `docs/adr/ADR-012-explosive-move-radar-boundary.md`
6. `docs/design/ATHENA-EXPLOSIVE-MOVE-RADAR-ROADMAP.md`
7. `docs/research/EM-1A-DATA-COVERAGE-AUDIT.md`
8. `docs/design/EM-1-RESEARCH-DATA-REMEDIATION-PLAN.md`
9. `docs/research/EM-1R2-CORPORATE-ACTION-COVERAGE-CONTRACT.md`
10. `docs/research/EM-1R2-CORPORATE-ACTION-COVERAGE-REPORT.md`
11. The EM-1r3 entry in `IMPLEMENTATION_SUMMARY.md`
12. `src/athena/explosive_move/`,
    `src/athena/data/intraday_reconstruction_ingestion.py`, and their focused
    tests

Read the live files. Do not infer current state from a prior chat summary.

## 3. Frozen boundaries

- EMR never contributes to canonical ATHENA scoring, confidence, risk,
  eligibility, Decision, TradePlan, or order behavior.
- No labels, features, base rates, models, rankings, scanners, or UI may be
  created before EM-1r5 approves a non-empty checkpoint set.
- Provider and network access belongs to the Data layer. EMR research and
  replay logic consume immutable persisted evidence only.
- Official NSE corporate-action filings/reports are authoritative for
  label-distorting actions. Kite is not a corporate-action authority.
- The current population is
  `ATHENA_CURRENT_CANONICAL_SURVIVOR_COHORT_V1`. It is survivor-cohort research,
  not point-in-time historical NSE-universe evidence.
- Current membership must never be projected backward. Survivorship-sensitive
  conclusions must display the limitation.
- Kite re-ingestion is the preferred authoritative intraday repair path.
  Deterministic normalization is allowed only when uniquely attributable.
- Never interpolate or synthesize OHLCV values. Missing or ambiguous evidence
  remains `UNKNOWN` or is excluded with a provenance reason.
- Replay, checksums, provenance, reason codes, and deterministic output
  identity are mandatory. Fail closed on uncertainty.
- Work on exactly one approved milestone and stop for owner review.

## 4. Approved evidence baseline

### EM-1r2

- Official NSE interval: 2023-08-11 through 2026-08-21.
- Retrieval coverage: 37 of 37 complete monthly slices and 7,330 source rows.
- Survivor cohort: 518 current canonical instruments.
- Materialized result: 2,009 accepted actions and 5,321 exclusions.
- Identical replay reproduced manifest and replay identities with zero
  duplicate inserts.

### EM-1r3

- Deterministic fixture: three symbol-sessions, four captured rows, one
  admitted session, and two admitted authoritative rows.
- Exclusions: one retrieval failure and one missing-slot session.
- Repair accounting: two authoritative re-ingestion rows, one identical
  duplicate collapse, one unrepaired missing slot, and zero interpolated or
  synthetic rows.
- Provider-free replay reproduced manifest identity; tampered source evidence
  was rejected.
- Validation: 8 focused tests passed; the full repository suite passed 2,145
  tests; focused Ruff checks and `git diff --check` passed.
- Repository-wide Ruff remains at the pre-existing baseline of 285 findings
  across 90 unrelated files.

The EM-1r3 numbers prove the reconstruction contract against deterministic
fixtures. They do not claim production-scale historical coverage.

### EM-1r4 (implemented 2026-08-22, awaiting owner approval -- not yet in the approved baseline above)

Unlike EM-1r2/EM-1r3, these are real production-scale numbers, not a
fixture: the service has no provider/network step, so running it against a
scratch copy of the real database (never the original) was cheap and gave
genuine evidence rather than a small deterministic sample.

- Cohort: 518 survivor-cohort instruments (identical to EM-1r2's own
  cohort -- unchanged since then).
- Study window actually exercised: 2026-01-01 through 2026-08-21 -- **not**
  EM-1r2's full 2023-08-11..2026-08-21 interval, because the real
  `config/calendar/*.json` currently only has holiday/expiry data loaded
  for 2026. This is a genuine, reported limitation discovered during
  verification, not a workaround chosen for convenience: any future EM-1r
  milestone enumerating historical sessions (EM-1r5, EM-1b) will hit the
  same wall until the calendar config is extended with historical years.
- Symbol-day admission: 81,326 assessed, 81,326 admitted, 0 excluded (both
  reasons are zero because no instrument in this ledger has a populated
  `listed_date`/`delisted_date` yet -- the exclusion contract and its test
  coverage exist and are proven correct on synthetic fixtures, they simply
  have nothing to catch in today's real data).
- Quote-timestamp hygiene: 196,461 quotes assessed for the 518 cohort
  instruments, 181,847 admitted, 511 rejected as Unix-epoch defaults, 0
  rejected as outside study bounds, **14,103 rejected as outside session
  bounds** -- a real, previously unmeasured data-quality finding (7.4%
  combined rejection rate). Worth investigating separately why this many
  quotes land outside 09:15-15:30 IST; EM-1r4 excludes them from research,
  it does not diagnose why they exist upstream.
- Deterministic replay reproduced an identical `replay_id` and
  `manifest_id` from the manifest's own frozen inputs (cohort, listing
  snapshot, and a content-addressed quote-snapshot artifact) -- confirmed
  to hold even after the live canonical tables were mutated between the
  original run and the replay (a dedicated regression test proves this,
  not just an assumption).
- A real bug found and fixed during this same verification pass: the
  ingestion service crashed (`CalendarError`) on any quote timestamp
  landing in a year the calendar engine has no data for -- exactly what
  happens for the real 1970 epoch-default rows, since no calendar config
  covers 1970. Fixed by treating "no calendar authority for this date" as
  a fail-closed exclusion (`TIMESTAMP_OUTSIDE_SESSION_BOUNDS`), never a
  crash -- proven non-vacuous the same way as every other guard in this
  track.
- Validation: 34 new tests (28 pure-contract in
  `tests/explosive_move/test_em1r4_cohort_admission.py`, 6 real-repository
  integration in `tests/data_layer/test_em1r4_cohort_admission_ingestion.py`,
  plus the calendar-coverage regression test added after the bug above),
  four proven non-vacuous; full repository suite passed 2,216 tests;
  focused Ruff clean on all new/changed files, repository-wide Ruff at the
  pre-existing 286-finding baseline (confirmed unrelated to this milestone
  by re-running with EM-1r4's own files excluded -- still 286); `git diff
  --check` passed.

## 5. EM-1r4 authorized scope

**Objective:** apply the frozen survivor-cohort contract to research admission
and enforce quote timestamp hygiene without pretending current membership is
historical membership.

The milestone must satisfy all of these acceptance criteria:

- every admitted symbol-day has dated eligibility evidence;
- current membership is never projected backward;
- listing or delisting ambiguity is excluded;
- the cohort name and limitation appear in every manifest and report;
- Unix-epoch and out-of-study or out-of-session quote timestamps are rejected;
- sector history remains `UNKNOWN` where no point-in-time authority exists;
- deterministic replay and immutable provenance remain intact;
- focused tests, the full suite, and static checks are reported.

## 6. EM-1r4 non-goals

Do not acquire point-in-time historical membership, add external data vendors,
generalize a data-cleaning platform, change the event or feature contracts,
create labels/features/base rates/models/rankings/scanners/UI, alter canonical
ATHENA outputs, or begin EM-1r5.

If EM-1r4 cannot fit the frozen boundaries, stop and propose an ADR. Do not
silently change architecture.

## 7. Required milestone closeout

Follow Design -> Implement -> Test -> Self-Validate -> Milestone Review
Summary -> owner review. Update `docs/MILESTONES.md`, this handoff,
`IMPLEMENTATION_SUMMARY.md`, the remediation plan, and `ATHENA_BRIEFING.md`
when the module map materially changes. Then stop and wait for owner approval.

The review summary must report cohort admission counts, timestamp rejection
counts by reason, listing/delisting ambiguity exclusions, `UNKNOWN` sector
counts, provenance/manifest evidence, deterministic replay verification,
focused and full test results, Ruff/static results, known limitations, and one
consolidated commit message.

## 8. Worktree discipline

The worktree may contain owner or prior-agent changes. Inspect it before
editing, do not revert unrelated work, and do not perform git write actions
unless the owner explicitly requests them for that instance.

## 9. Continuation prompt

> Read `ATHENA_BRIEFING.md` and `docs/ATHENA-EMR-HANDOFF.md` first, then verify
> the EMR section in `docs/MILESTONES.md` and every frozen contract referenced
> by the handoff. EM-1r3 is owner-approved. Proceed with EM-1r4 only: cohort
> admission and quote timestamp hygiene under ADR-012 and the survivor-cohort
> claim boundary. Do not acquire point-in-time membership, create labels,
> features, models, scanners, or UI, alter canonical ATHENA outputs, or begin
> EM-1r5. Follow the milestone workflow, run focused and full validation,
> update all related EMR docs, stop after the EM-1r4 Milestone Review Summary,
> and wait for owner approval.
