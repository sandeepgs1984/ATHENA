# ATHENA Explosive Move Radar Handoff

**Snapshot:** 2026-09-01 (EM-5 scanner contract ACCEPTED; Tuesday Track B
live capture phase owner-approved; Track B.1 zero-off-grid contract-gap
correction implemented; corrected classification
`NO_OFF_GRID_PROVISIONAL_OBSERVED`; EM-5 owner review pending)
**Governing boundary:** ADR-012
**Current state:** EM-0 through EM-4E are all owner-approved (GO), including
the sealed FINAL_TEST evaluation. EM-5 (the replayable bulk-input live
scanner, no UI) has its contract `ACCEPTED` by Owner/Chief Architect
(2026-08-28) and is functionally complete pending exactly one open
blocker: **current-day live M5 semantics**. Real M5 timestamps still drift
off-grid after ~09:35-09:40 in the *current* (still-forming) trading
session specifically — prior-day/settled data is now clean (see the
ID-track's own ID-5A repair, §7 below, for the mechanism that fixed
settled-day drift). Track B's live provisional-vs-settled capture/compare/
classify tooling
(`src/athena/data/live_m5_provisional_settlement_diagnostic.py`,
`src/athena/data/em5_track_b_capture_cli.py`) is built and unit-tested.
Artifact inspection on **Monday 2026-08-31 15:39 IST** found no EM-5 Track B
live capture files; all nine frozen checkpoints were therefore
`NOT_OBSERVED_LIVE` for that date. On **Tuesday 2026-09-01**, the
owner-authorized live capture completed for the frozen 9-symbol sample across
all 9 checkpoints and the owner approved that live-capture phase: 81/81 raw Kite files, 0 provider failures, 0
`NOT_OBSERVED_LIVE` checkpoints, and 0 off-grid raw `ts_open` values. The
owner-authorized settled-provider comparison was run through the existing
Track B settlement path with the implementation's explicit `force=True`
override because the 21-day settlement guard did not pass on 2026-09-01. The
report completed, but its original classification was `null`: the frozen Track
B classifier only classified eligible off-grid provisional rows, and this
canary had none. Track B.1 adds the explicit observational outcome
`NO_OFF_GRID_PROVISIONAL_OBSERVED` for a complete successful canary with zero
off-grid provisional rows. Raw-only replay of the immutable Tuesday evidence
now produces that corrected classification. Recommendation: the specific
`CANARY_BLOCKED_LIVE_M5_SEMANTICS` blocker can clear for this frozen canary,
but EM-5 is not closed until owner review. This is not FAILED and does not
authorize EM-6.

**Read `docs/ATHENA-ID-TRACK-HANDOFF.md` §7 before touching anything on
Monday.** The ID-track's own ID-5B milestone ("Live Current-Session M5
Semantics Canary") investigates the *exact same* real-world Kite
provisional-M5 phenomenon, using shared low-level diagnostic primitives
in `athena.data` — but with a **different instrument canary** (ID-5B: 1
benchmark index + 2 sector indexes + 2 equities; EM-5 Track B: 9 equities
across 3 liquidity buckets, `DEFAULT_SYMBOL_LIQUIDITY_BUCKETS` in
`em5_track_b_capture_cli.py`) and a **separate consuming decision** (EM-5
decides whether its own live scanner can trust current-session M5 for its
checkpoint gates; ID-5B decides how ATHENA-core's `session_stage`/VWAP/
ORB/RelativeStrength/RelativeVolume should treat current-session
provisional M5 going forward). Both are architecturally isolated (see §8)
but will each need their own real Kite capture run on Monday — plan the
capture sequencing so they don't collide on the same request budget or
misattribute one track's evidence to the other's decision.

## 1. Current milestone state

| Milestone | State |
|---|---|
| EM-0 | Owner-approved 2026-08-21 |
| EM-1a | Owner-approved 2026-08-21; superseded by EM-1r5's real re-audit (all 9 checkpoints now accepted) |
| EM-1r1 | Owner-approved 2026-08-21 |
| EM-1r2 | Owner-approved 2026-08-21 |
| EM-1r3 | Owner-approved 2026-08-21; corrected production sweep COMPLETE 2026-08-26 (92.81% admission, replay-verified) |
| EM-1r4 | Owner-approved 2026-08-22 |
| EM-1r5 | Owner-approved 2026-08-26 — all 9 candidate checkpoints accepted (research-ready evidence only) |
| EM-1b | Owner-approved 2026-08-27 — dataset generated, chronological partitions assigned |
| EM-1c prerequisite | Owner-approved 2026-08-27 — real NIFTY 50/INDIA VIX regime evidence acquired and replayed, 743/743 sessions classified, 0 UNKNOWN |
| EM-1c | Owner-approved 2026-08-27 — unconditional base rates published (TRAIN-only); minimum cohort support frozen (n≥1,000, k≥10) |
| EM-2 | Owner-approved 2026-08-27 — cutoff-safe 28-field evidence contract (em2-evidence-v1) generated for TRAIN |
| EM-3 v1 | Owner-approved 2026-08-27 — univariate checkpoint-level TRAIN conditional analysis, 185,004 cells, 14,727 EXPLORATORY_CANDIDATE |
| EM-4A | Owner-approved 2026-08-27 — deterministic evidence score (frozen vote rules) |
| EM-4B | Owner-approved 2026-08-27 — 18 pooled logistic baselines fit (TRAIN-only, chronological CV), all converged |
| EM-4C | Owner-approved (GO) 2026-08-28 — logistic beats deterministic on PR-AUC in 18/18 real combinations on real VALIDATION |
| EM-4D | Owner-approved (GO) 2026-08-28 — all 162 (family×threshold×checkpoint) cells Platt-calibrated |
| EM-4E | Owner-approved / GO 2026-08-28 — sealed FINAL_TEST evaluation complete (702,702 rows, 157 sessions); calibrated logistic beats deterministic 18/18, replicating VALIDATION on a third, never-before-touched partition. FINAL_TEST remains sealed |
| EM-5 | **TRACK B.1 READY FOR OWNER REVIEW — RECOMMEND EM-5 CLOSURE** — contract ACCEPTED 2026-08-28. Regime wiring RESOLVED; REL_VOLUME_C historical support REPAIRED (real backfill, 23/23 resolvable prior sessions across all 3 liquidity tiers). Tuesday 2026-09-01 Track B live capture phase is owner-approved (81/81 Kite raw files, 0 provider failures, 0 `NOT_OBSERVED_LIVE`, 0 off-grid raw `ts_open`). Owner-authorized settled-provider comparison ran through the existing `force=True` override and originally produced `classification=null` because the frozen classifier had no eligible off-grid rows to classify. Track B.1 adds `NO_OFF_GRID_PROVISIONAL_OBSERVED`; raw-only replay classifies Tuesday as that outcome. Recommendation: clear `CANARY_BLOCKED_LIVE_M5_SEMANTICS`; no additional Track B live canary required; EM-5 ready for owner approval/closure. EM-5 remains open until owner approval |
| EM-6 | Planned — add EMR research UI only after scanner approval |
| EM-7 | Planned — isolated shadow validation, OFF-vs-shadow comparison |
| EM-8 | Planned — research-only / continued shadow / retirement / new integration ADR decision |

EMR remains isolated research. Nothing completed so far changes ATHENA's UI,
score, confidence, risk, eligibility, Decision, TradePlan, scanner, broker, or
order behavior. **Re-verified 2026-08-30** (see §8) alongside the ID-track's
own point-in-time-safety milestones — zero cross-track code coupling found.

EM-4E is owner-approved / GO as of 2026-08-28. Do not re-read, rerun, or
reanalyze FINAL_TEST without fresh, explicit owner authorization; it remains
sealed. Do not start EM-6 without a fresh, explicit owner instruction. EM-5's
own canary blocker is independent of the EM-4E GO decision — do not conflate
the two.

## 2. Mandatory read order

1. `ATHENA_BRIEFING.md`
2. The Explosive Move Radar section of `docs/MILESTONES.md` (read the
   whole section — it is long, and the live status table above is a
   condensed pointer, not a substitute)
3. `docs/ATHENA-ID-TRACK-HANDOFF.md` §7-8 (the shared Monday dependency
   and the isolation-verification finding) — **mandatory even for EMR-only
   work**, since Monday's live capture touches both tracks
4. ATHENA-002 Sections 2 and 19 and their Definition of Done constraints
5. `docs/adr/ADR-011-canonical-symbol-master-and-universes.md`
6. `docs/adr/ADR-012-explosive-move-radar-boundary.md`
7. `docs/design/ATHENA-EXPLOSIVE-MOVE-RADAR-ROADMAP.md`
8. `docs/design/EM-5-LIVE-SCANNER-CONTRACT.md` (§14's fail-fast production
   canary gate — the one EM-5's `CANARY_BLOCKED_LIVE_M5_SEMANTICS` status
   refers to)
9. The EM-4E and EM-5 entries in `IMPLEMENTATION_SUMMARY.md` (top entries —
   do not read the whole file, it is a permanent, ever-growing log)
10. `src/athena/explosive_move/`, `src/athena/data/em5_track_b_capture_cli.py`,
    `src/athena/data/live_m5_provisional_settlement_diagnostic.py`, and
    their focused tests

Read the live files. Do not infer current state from a prior chat summary.

## 3. Frozen boundaries

- EMR never contributes to canonical ATHENA scoring, confidence, risk,
  eligibility, Decision, TradePlan, or order behavior.
- No production recommendation, canonical score input, or UI may be built
  before EM-5's canary blocker closes and EM-6 is explicitly authorized.
- Provider and network access belongs to the Data layer. EMR research and
  replay logic consume immutable persisted evidence only.
- Official NSE corporate-action filings/reports are authoritative for
  label-distorting actions. Kite is not a corporate-action authority.
- The current population is
  `ATHENA_CURRENT_CANONICAL_SURVIVOR_COHORT_V1`. It is survivor-cohort research,
  not point-in-time historical NSE-universe evidence.
- Current membership must never be projected backward. Survivorship-sensitive
  conclusions must display the limitation.
- FINAL_TEST is sealed — EM-4E's read was the one-shot evaluation. Do not
  re-read FINAL_TEST for any reason without fresh, explicit owner
  authorization.
- Never interpolate or synthesize OHLCV values. Missing or ambiguous evidence
  remains `UNKNOWN` or is excluded with a provenance reason.
- Replay, checksums, provenance, reason codes, and deterministic output
  identity are mandatory. Fail closed on uncertainty.
- Track B's live capture never writes to `db/athena.db` or `db/emr.db` —
  raw captures are plain JSON files, by design (see
  `live_m5_provisional_settlement_diagnostic.py`'s own module docstring).
  Do not "improve" this into a database write without fresh owner
  authorization — it is a deliberate contamination guard.
- No timestamp rounding, flooring, ceiling, or nearest-match anywhere in
  Track B's comparison logic — a provisional row maps to a settled bucket
  only by exact OHLCV content match.
- Work on exactly one approved milestone and stop for owner review.

## 4. Approved evidence baseline

See `IMPLEMENTATION_SUMMARY.md`'s EM-1r2 through EM-4E entries and
`docs/MILESTONES.md`'s Explosive Move Radar section for the full,
detailed evidence baseline for every closed milestone (EM-1r2's corporate-
action coverage, EM-1r3's production capture numbers, EM-1r4's cohort-
admission/quote-hygiene numbers, EM-1r5's re-audit, EM-1b's partitions,
EM-1c's base rates, EM-2's evidence contract, EM-3's conditional analysis,
EM-4A-E's scoring/model/calibration/FINAL_TEST results). This handoff does
not reproduce those numbers — it is a navigation aid, not a substitute for
reading the live documents.

## 5. EM-5 authorized scope (current active milestone)

**Objective:** implement and validate a replayable, bulk-input live
scanner (no UI) over EM-4E's frozen calibrated models, gated by a
real-provider production canary, before any UI or shadow-validation work
begins.

Accepted so far (contract ACCEPTED, Owner/Chief Architect, 2026-08-28):

- Regime wiring: RESOLVED. Real canonical `RegimeEngine` wired in, proven
  against real data (518/518 instruments' regime fields known, genuine
  non-UNKNOWN labels).
- REL_VOLUME_C historical support: REPAIRED. Real Owner-authorized
  backfill (537 instruments × 31 days, real backup taken first)
  eliminated 1,051,481 off-grid M5 candles and lifted REL_VOLUME_C's
  resolvable prior-session count from 12-14/23 to 23/23 (need ≥20) across
  all three liquidity tiers sampled. A real production canary at the two
  checkpoints unaffected by the still-open live-M5 question now genuinely
  PASSES (100% completeness, real 518-instrument universe).
- Current-day live M5 semantics: **Track B.1 correction ready for owner
  review; recommendation is to clear the live-M5 semantics blocker.** See
  §1/§6.

## 6. EM-5's one remaining blocker — Track B

Track B (`src/athena/data/live_m5_provisional_settlement_diagnostic.py` +
`src/athena/data/em5_track_b_capture_cli.py`) answers: what does a
provisional M5 row observed *during* a live session actually represent —
a mislabeled bucket (timestamp-only drift) or genuinely different OHLCV
content once settled? Never assumed by convention; answered empirically,
content-match only.

**Live execution plan (already frozen, built, unit-tested; Tuesday 2026-09-01
live capture completed):**

1. `run_preflight` — calendar, Kite auth (one real minimal call), disk
   space. Any failure raises `PreflightError`; do not proceed on partial
   preflight.
2. `run_capture_phase` at each of the 9 frozen time checkpoints
   (`TRACK_B_CHECKPOINT_SCHEDULE`: 09:20, 09:30, 09:45, 10:00, 10:30,
   11:00, 12:00, 13:00, 14:00) for the 9-symbol liquidity-bucketed sample
   (`DEFAULT_SYMBOL_LIQUIDITY_BUCKETS`: 3×high/3×medium/3×low). Idempotent
   and restart-safe — a checkpoint already captured on disk is never
   re-fetched; a checkpoint whose live window has passed by more than
   `MAX_CHECKPOINT_OBSERVATION_DELAY_SECONDS` (300s) is recorded
   `NOT_OBSERVED_LIVE`, never fabricated.
3. `run_settlement_comparison_phase` — only once the day is genuinely
   settled (`is_likely_settled`, or an explicit override), re-fetch the
   same sessions and produce the classification report via exact-content
   matching.
4. `classify_diagnosis` — one of `TIMESTAMP_ONLY_PROVISIONAL_DRIFT` /
   `PROVISIONAL_OHLCV_ALSO_CHANGES` / `MAPPING_AMBIGUOUS`, read off the
   real comparison, never assumed.

**Coordinate with the ID-track before capturing.** ID-5B needs its OWN
5-instrument canary (benchmark + 2 sector indexes + 2 equities) — a
DIFFERENT sample than Track B's 9 equities. Confirm with whoever is
running ID-5B whether Monday's session runs one shared capture covering
both samples, or two independent captures, before spending Kite request
budget twice on overlapping instruments. See
`docs/ATHENA-ID-TRACK-HANDOFF.md` §7 for the open question as framed from
the ID-track's side — it is the same question from this side.

**Monday 2026-08-31 status:** no EM-5 Track B live capture artifacts were
found in `artifacts/`, and all nine frozen checkpoints had elapsed by more
than 300 seconds when checked at `Mon Aug 31 15:39:33 IST 2026`. The
checkpoint statuses for Monday are therefore honestly recorded as
`NOT_OBSERVED_LIVE`; see
`docs/research/EM-5-TRACK-B-LIVE-M5-CAPTURE-2026-08-31.md`. ID-5B's
separate five-instrument artifacts must not be substituted for EM-5 Track B's
nine-equity liquidity-bucket sample.

**Tuesday 2026-09-01 status:** owner-authorized live capture completed via the
existing unattended runner under `caffeinate` and the owner approved the live
capture phase; final raw artifacts live under
`artifacts/live/em5_track_b/2026-09-01/`, with the evidence note at
`docs/research/EM-5-TRACK-B-LIVE-M5-CAPTURE-2026-09-01.md`. The
owner-authorized settled comparison produced
`em5-track-b-20260901__settlement_comparison.json` with SHA-256
`974531de8703982fcab49d15924b21e986728e0fd4c2759b034af36f6345a0a1` and
the original pre-B.1 `classification=null` because no off-grid provisional rows
were available for the frozen Track B classifier. Track B.1 raw-only replay
classifies the same immutable evidence as
`NO_OFF_GRID_PROVISIONAL_OBSERVED`. EM-5 remains open pending owner review.

## 7. EM-5 non-goals (still in force)

Do not: build the EM-6 UI, feed EMR output into canonical ATHENA scoring/
confidence/risk/Decision/TradePlan, re-read FINAL_TEST, round/floor/
ceiling/nearest-match any timestamp anywhere in Track B, synthesize or
interpolate any OHLCV value, delete or overwrite a current-session row in
`db/athena.db` (that is the ID-track's `db/athena.db` — EM-5 does not own
it and must not repair it), or begin EM-6/EM-7/EM-8 without a fresh,
explicit owner instruction closing EM-5's blocker first.

If EM-5's Track B evidence reveals a genuine architectural limitation
(e.g. content changes so pervasively that no runtime treatment is safe),
stop and propose an ADR. Do not silently work around it.

## 8. Cross-track isolation — verified 2026-08-30

Re-verified directly against the actual source tree while ID-5E/5F/5G/5G.1
(candle/quote/snapshot point-in-time retrieval safety) were implemented on
the ID-track, in the same session as this handoff's update:

- `grep`-confirmed zero references to `explosive_move` anywhere in
  `src/athena/session/`, `src/athena/intraday/`, or the two files ID-5E/
  5F/5G/5G.1 modified (`src/athena/data/store/repository.py`,
  `src/athena/ops/owner_validation.py`).
- `grep`-confirmed EMR's own code (`src/athena/explosive_move/` plus the
  EM-prefixed scripts under `src/athena/data/`) never calls
  `list_candles_recent`, `get_latest_quote`, `get_latest_snapshot`,
  `get_latest_snapshot_as_of`, or `get_latest_snapshot_before` — the exact
  repository methods ID-5E/5F/5G/5G.1 changed. EMR reads candles via its
  own methods (`get_candles`, `candles_for_instruments`) and its own
  dedicated EM-specific ingestion services — zero behavioral exposure to
  any ID-track repository change.
- `db/emr.db` and `db/athena.db` are separate files; EMR's own
  `src/athena/explosive_move/store/` schema is independent of ATHENA-core's
  candles/quotes/market_snapshots tables.
- The one apparent shared surface — Track B's diagnostic living in
  `src/athena/data/` rather than `src/athena/explosive_move/` — is a
  **shared, neutral, read-only, non-mutating data-layer utility** (writes
  nothing to either database; captures persist as plain JSON), not a
  business-logic coupling. It answers one real-world empirical question
  (Kite's provisional-M5 settle-lag) that happens to matter to both
  tracks' own separate downstream decisions. This is the one place the two
  tracks' Monday work actually touches — see §6's coordination note.

**Conclusion: the two tracks are architecturally isolated** (no shared
business logic, no shared schema, no shared scoring/Decision/TradePlan
effect) but share one underlying empirical question and one diagnostic
tool, and will need coordinated (not necessarily combined) real-Kite
captures on Monday.

## 9. Required milestone closeout

Follow Design -> Implement -> Test -> Self-Validate -> Milestone Review
Summary -> owner review. Update `docs/MILESTONES.md`, this handoff,
`IMPLEMENTATION_SUMMARY.md`, the roadmap doc, and `ATHENA_BRIEFING.md`
when the module map materially changes. Then stop and wait for owner
approval.

The Track B review summary must report: preflight results, per-checkpoint
capture status (CAPTURED/ALREADY_CAPTURED/NOT_OBSERVED_LIVE/NOT_YET_DUE),
settlement-comparison field-by-field OHLCV differences per instrument/
checkpoint, the classification (`TIMESTAMP_ONLY_PROVISIONAL_DRIFT` /
`PROVISIONAL_OHLCV_ALSO_CHANGES` / `MAPPING_AMBIGUOUS`), the resulting
canary-gate status, focused and full test results, and one consolidated
commit message.

## 10. Worktree discipline

The worktree may contain owner or prior-agent changes (this session's own
ID-5* changes are already present and committed/staged — do not revert
them; they belong to the ID-track, not EMR). Inspect it before editing, do
not revert unrelated work, and do not perform git write actions unless the
owner explicitly requests them for that instance.

## 11. Continuation prompt

> Read `ATHENA_BRIEFING.md` and `docs/ATHENA-EMR-HANDOFF.md` first, then
> verify the EMR section in `docs/MILESTONES.md`, EM-5's exact current
> status, and `docs/ATHENA-ID-TRACK-HANDOFF.md` §7-8 for the shared-Monday-
> dependency context. EM-4E is owner-approved / GO and EM-5's contract is
> ACCEPTED but blocked on Track B. If today is a real, live
> NSE trading day (verify via `date` — do not assume), and the owner has
> authorized it, execute Track B's live capture
> (`src/athena/data/em5_track_b_capture_cli.py`): run preflight, capture at
> all 9 frozen checkpoints for the 9-symbol liquidity sample, and (once the
> day is settled — likely a later session, not the same day) run the
> settlement-comparison phase and classify the result. Coordinate with the
> ID-track's own ID-5B canary before spending Kite request budget — confirm
> whether captures are shared or separate. Do NOT round/floor/ceiling/
> nearest-match any timestamp, synthesize any OHLCV value, touch
> `db/athena.db`, re-read FINAL_TEST, or begin EM-6/7/8. Follow the
> milestone workflow, update all related EMR docs, stop after the Track B
> Milestone Review Summary, and wait for owner approval.
