# ATHENA Intraday Intelligence (ID-Track) Handoff

**Snapshot:** 2026-09-02 (ID-5B final settled-provider classification
owner-approved and CLOSED; ID-5 owner-approved and CLOSED; ID-6 discovery
architecture owner-approved with condition; ID-6A0 Entry Qualification ADR
ready for owner review)
**Governing boundary:** proposed `docs/adr/ADR-013-entry-qualification-architecture.md`
for Entry Qualification; otherwise this track extends the existing frozen
`ATHENA-002-System-Blueprint.md` module map (§6 of `ATHENA_BRIEFING.md`).
**Current state:** ID-0 through ID-5G.1 are all owner-approved. ID-5B
(Live Current-Session M5 Semantics Canary) captured the **Monday
2026-08-31** frozen 5-instrument canary, ID-5B.1 corrected the
forming-vs-closed CASE classifier, and the owner approved the final
settled-provider classification `CASE_B_CONTENT_CHANGES` on 2026-09-01.
ID-5B is CLOSED and ID-5 is CLOSED. ID-6 discovery architecture is
owner-approved with condition: ID-6A0 must be approved before any ID-6A
implementation. The ID-6A0 Entry Qualification ADR is ready for owner review;
no production behavior has been implemented.
Evidence notes:
`docs/research/ID-5B-LIVE-M5-SEMANTICS-CAPTURE-2026-08-31.md` and
`docs/research/ID-6-SCOPE-ARCHITECTURE-DESIGN.md`.

**Read `docs/ATHENA-EMR-HANDOFF.md` §6/§8 before touching anything on
Monday.** EMR's own EM-5 milestone has an *independent* open blocker
(Track B) investigating the *same* real-world Kite provisional-M5
phenomenon ID-5B investigates — but with a *different* instrument canary
and a *different* consuming decision. See §7-8 below for the full detail;
do not start ID-5B's capture without first checking whether EMR's own
Track B capture is running the same morning.

## 1. Current milestone state

| Milestone | State |
|---|---|
| ID-0 | Owner-approved with conditions 2026-08-29 — runtime audit; GO WITH CONDITIONS, addressed by ID-P0/ID-P0.1 |
| ID-P0 | Owner-approved 2026-08-29 — ADR-003 dormant-vs-live ambiguity resolved, Sector Health wired into live scoring/evidence/decision |
| ID-P0.1 | Owner-approved 2026-08-29 — measured real historical impact of activating Sector Health; no threshold recalibration |
| ID-1 | Owner-approved 2026-08-29 — `athena.session` package: `SessionContext`, completed-candle semantics, session-data-quality UNKNOWN |
| ID-2 | Architecture accepted 2026-08-29 — `IntradaySignalSet`/`IntradayTrendContext`, not fully closed until ID-2.1 |
| ID-2.1 | Owner-approved 2026-08-29 — completed-candle correctness fix for VWAP/confluence; `NEUTRAL`→`MIXED` rename |
| ID-3 | Architecture + ORB contract accepted 2026-08-29 — not fully closed until ID-3.1 |
| ID-3.1 | Owner-approved 2026-08-29 — fixed shared `list_candles_recent(limit=100)` truncation and ORB slot-count-vs-canonical-slot completeness |
| ID-4 | Architecture accepted 2026-08-29 — `RelativeStrengthContext`, not fully closed until ID-4.1 |
| ID-4.1 | Owner-approved 2026-08-29 — fixed comparable-constituent cutoff bug (opening-only constituents wrongly capping the cutoff) |
| ID-5 | **OWNER APPROVED / CLOSED 2026-09-01** — umbrella milestone for core index M5 data-quality. ID-5A, ID-5B, ID-5C, ID-5D/ID-5D.1, ID-5E, ID-5F, and ID-5G/ID-5G.1 together complete the data-foundation milestone |
| ID-5A | Owner-authorized, EXECUTED and CLOSED 2026-08-29 — real settled-session M5 repair for 2026-08-28, 537/537 instruments, 0 failures |
| ID-5B | **OWNER APPROVED / CLOSED 2026-09-01** — final settled-provider classification accepted as `CASE_B_CONTENT_CHANGES`. Live Current-Session M5 Semantics Canary captured 25 raw files on 2026-08-31 for the frozen 5-instrument canary; owner approved the capture phase. ID-5B.1 corrected classification to partition `FORMING_AT_CAPTURE`, `CLOSED_AT_CAPTURE`, and `OFF_GRID_PROVISIONAL` using actual `request_ts` plus `is_candle_completed`; forming changes no longer count as CASE B/C, and the owner approved that correction. The owner-authorized settled-provider comparison found 18 forming-at-capture rows changed, 704 closed-at-capture rows stable by unique exact OHLCV mapping, 1 eligible closed-at-capture row with no exact settled OHLCV candidate (`NSE:NIFTY 50`, `13:55`, captured at `14:00:01`), 0 off-grid rows, and 0 ambiguous mappings. No additional live canary is required for closure. See `docs/research/ID-5B-LIVE-M5-SEMANTICS-CAPTURE-2026-08-31.md` |
| ID-5C | Owner-approved 2026-08-29 — `GapContext` (previous-session-close→current-session-open), D1-only, independent of ID-5B |
| ID-5D | Architecture/methodology accepted 2026-08-29 — `RelativeVolumeContext`, not fully closed until ID-5D.1 |
| ID-5D.1 | Owner-approved 2026-08-29 — current-window contiguity + retrieval-policy (`earliest_candle_ts`) correctness fixes |
| ID-5E | Owner-approved 2026-08-30 — `list_candles_recent(..., as_of=...)` market-time point-in-time safety for candles |
| ID-5F | Owner-approved 2026-08-30 — `get_latest_quote(..., as_of=...)` market-time point-in-time safety for quotes |
| ID-5G | Architecture accepted 2026-08-30 — `get_latest_snapshot_as_of(as_of)` for MarketSnapshot, not fully closed until ID-5G.1 |
| ID-5G.1 | Owner-approved 2026-08-30 — full sub-second, offset-safe precision fix for both snapshot point-in-time methods |
| ID-6 | DISCOVERY ARCHITECTURE OWNER APPROVED WITH CONDITION 2026-09-02 — corrected architecture accepted, conditional on owner approval of ID-6A0 before any ID-6A implementation |
| ID-6A0 | READY FOR OWNER ADR REVIEW 2026-09-02 — standalone Entry Qualification Architecture ADR proposed at `docs/adr/ADR-013-entry-qualification-architecture.md`; documentation/governance only, no production code |

The full detailed evidence for every closed milestone above is in
`docs/MILESTONES.md`'s "Intraday Intelligence Track" section (long — this
table is a navigation aid, not a substitute) and in the corresponding
dated entries of `IMPLEMENTATION_SUMMARY.md` (newest-first; read the
specific milestone's own entry, not the whole file).

## 2. Mandatory read order

1. `ATHENA_BRIEFING.md`
2. The Intraday Intelligence Track section of `docs/MILESTONES.md` (read
   the whole section)
3. `docs/ATHENA-EMR-HANDOFF.md` §6/§8 (the shared Monday dependency and
   the isolation-verification finding) — mandatory even for ID-track-only
   work, since Monday's live capture touches both tracks
4. `docs/research/ID-0-RUNTIME-AUDIT-ARCHITECTURE-REPORT.md` — the
   original architecture audit this whole track is built on
5. The ID-5A, ID-5C, ID-5D.1, ID-5E, ID-5F, ID-5G.1 entries in
   `IMPLEMENTATION_SUMMARY.md` (top entries for each — do not read the
   whole file, it is a permanent, ever-growing log)
6. `src/athena/session/`, `src/athena/intraday/`, the relevant sections
   of `src/athena/ops/owner_validation.py` (`session_stage`,
   `intraday_analytics_stage`, `relative_strength_stage`,
   `relative_volume_stage`), and their focused tests

Read the live files. Do not infer current state from a prior chat summary
— this document itself is a snapshot and will go stale.

## 3. Frozen boundaries

- No order-placement code, ever, under any milestone.
- No BUY/SELL score, no trade probability, no EntryQualification exists
  anywhere in this track yet — every artifact so far
  (`SessionContext`/`IntradaySignalSet`/`OpeningRangeEvidence`/
  `RelativeStrengthContext`/`GapContext`/`RelativeVolumeContext`) is
  analytical evidence only, never a Decision-gate input.
- Nothing in this track has changed scoring/confidence/risk/Decision/
  TradePlan formulas, weights, or thresholds — every fix has been input-
  correctness/retrieval-timing only.
- Point-in-time retrieval safety (ID-5E/5F/5G/5G.1) is MARKET-TIME safety
  only. Knowledge-time/bitemporal replay (reconstructing exactly what
  ATHENA knew at a past instant, including a since-corrected provisional
  value) remains explicitly unsupported — do not claim otherwise.
- `earliest_candle_ts`/`list_candles_recent`/`get_latest_quote`/
  `get_latest_snapshot_as_of`/`get_latest_snapshot_before` all have frozen
  contracts now (see §6 of `docs/ATHENA-TECHNICAL-ARCHITECTURE.md`'s §9
  item 17) — do not re-litigate their semantics (inclusive `<=` vs strict
  `<`, full sub-second precision, offset safety) without a fresh, explicit
  owner instruction.
- `RelativeVolumeEngine`'s baseline policy is "use ALL available
  comparable prior settled sessions," no hardcoded N. A rolling-baseline-
  cap policy question is explicitly OWNER_DEFERRED — do not decide it
  silently.
- ID-5B must not: round/floor/ceiling/nearest-match any timestamp,
  resample, normalize provisional timestamps, forward-fill, synthesize
  candles, substitute quotes for candles, repair/delete/overwrite
  current-session rows, or introduce any runtime canonicalization/RS/ORB/
  RVOL workaround. It is measurement/classification work only — see §7.
- Never write to `db/athena.db` except via explicit, per-instance owner
  authorization (as happened for ID-5A) or via `sqlite3.Connection.backup()`
  into a scratch copy for read-only investigation, deleted after use.
- Work on exactly one approved milestone and stop for owner review. Never
  auto-continue past an approval gate.

## 4. Approved evidence baseline

See `IMPLEMENTATION_SUMMARY.md`'s dated entries (ID-1 through ID-5G.1) and
`docs/MILESTONES.md`'s Intraday Intelligence Track section for the full
evidence baseline of every closed milestone: ID-1's `SessionContext`
foundation, ID-2.1's completed-candle correctness proof, ID-3.1's
canonical-slot-integrity real-data check (OR15 526/526 COMPLETE, OR30
526/526 after ID-5A), ID-4.1's comparable-constituent fix, ID-5A's real
settlement-repair run (537/537 succeeded), ID-5C's real Gap distribution
(526/527 available), ID-5D.1's real RVOL replay (526/527 available across
3 cutoffs, zero point-in-time violations), and ID-5E/5F/5G.1's own
non-vacuous point-in-time-safety proofs (a real SMA(20) becoming `999999`,
a real confluence signal flipping to unavailable, a real
`latest_quote_ts`/`MarketSnapshot.india_vix` leaking a future value — each
before its respective fix, restored after). This handoff does not
reproduce those numbers.

## 5. Full test suite status

As of the ID-5G.1 close (2026-08-30): **2,935 passed, 1 pre-existing
skip**, 0 failed. Ruff clean for every ID-track file (a small number of
pre-existing, unrelated `repository.py` SIM117 findings remain, confirmed
present before this track ever touched the file). Zero new mypy failures
introduced by any ID-track milestone (mypy is not part of this repo's
`strict` file list for `owner_validation.py`/`repository.py`, but every
session in this track tracked and reported its own delta against the
pre-existing baseline rather than ignoring it).

## 6. ID-6 / ID-6A0 — current architecture gate

ID-6 discovery/design is complete and hardened as of 2026-09-02:
`docs/research/ID-6-SCOPE-ARCHITECTURE-DESIGN.md`.

Owner review decision: ID-6 discovery architecture is owner-approved with
condition. The required condition is ID-6A0, an Entry Qualification
Architecture ADR, before ID-6A production code. The proposed standalone ADR is
`docs/adr/ADR-013-entry-qualification-architecture.md` and is ready for owner
ADR review.

The approved architecture treats current-session completed M5 as provisional
for qualification purposes after ID-5B's accepted
`CASE_B_CONTENT_CHANGES` result; state and reliability are orthogonal; and no
irreversible ID-6 state may be caused directly or indirectly solely by
live-M5-provisional evidence. Do not implement ID-6A contracts, an engine,
persistence, UI, thresholds, IntradayTradePlan, ID-7, EM-6, EMR, DarvaX, or
order behavior until the owner approves ID-6A0 and explicitly authorizes the
next milestone.

## 7. ID-5B — closed result

**Objective:** determine what Kite's current-session provisional M5 rows
actually mean — timestamp-only drift (a mislabeled bucket that settles to
the same OHLCV) or genuine content change (OHLCV itself differs once
settled) — before ATHENA-core adopts any runtime treatment of
current-session M5 data. This is measurement/classification work, not a
trading-methodology milestone.

**Frozen canary scope:** 1 benchmark index + 2 sector indexes + 2
equities — deliberately small; do not broaden to the full universe merely
because infrastructure now supports it.

**Classification framework (do not invent another):**

- **CASE A — TIMESTAMP_ONLY**: the provisional/off-grid representation
  changes its timestamp/placement when settled, but the underlying OHLCV
  content for the conceptual interval is materially the same.
- **CASE B — CONTENT_CHANGES**: the provisional candle's OHLCV content
  materially changes when the interval/provider data settles.
- **CASE C — MIXED**: some intervals/instruments behave timestamp-only
  while others materially change content, or behavior is otherwise
  inconsistent.
- **CASE D — INSUFFICIENT_EVIDENCE**: the captured observations are
  insufficient to classify the provider semantics safely.

**Method (raw evidence only — do not deviate):** capture raw provider
responses at multiple live-session checkpoints for the frozen 5-instrument
canary; track (1) provisional/forming observations, (2) interval-closed-
but-potentially-unsettled observations, (3) later observations after
provider settlement; compare the SAME conceptual M5 interval across those
states by exact OHLCV content match, never nearest-timestamp or
bucket-floor reasoning. Record: instrument, provider/raw timestamp,
observation timestamp, conceptual interval being compared, O/H/L/C/V,
whether the interval should already be closed at observation time, later
settled timestamp, later settled OHLCV, field-by-field differences, and
classification evidence.

**Also report (observational only, do not modify these engines to
compensate):** at selected checkpoints, what ATHENA can genuinely compute
from canonical completed data at that instant — `SessionContext`, VWAP,
OR15, OR30, `RelativeStrengthContext`, `RelativeVolumeContext`
availability/state. This quantifies the real operational impact of
provider settlement lag; it does not change any of those engines.

**Tooling used:** ID-5B used the small ID-specific wrapper
`src/athena/data/id5b_live_m5_semantics_canary.py` around the shared
read-only primitive
`src/athena/data/live_m5_provisional_settlement_diagnostic.py`. This
preserved ID-5B's own frozen 5-instrument canary, manifest/report names,
request budgets, and CASE A/B/C/D mapping while keeping EM-5 Track B
evidence separate.

**Closed result:** final owner-approved classification is
`CASE_B_CONTENT_CHANGES`. The correct engineering conclusion is narrow:
current-session Kite M5 evidence can differ from the later settled
historical representation even after a candle satisfied ATHENA's
deterministic completed-candle boundary. This does not establish that all
current-session M5 candles are unstable, that Kite always changes
completed candles, or that Kite always returns off-grid timestamps. In
this canary, 704/705 eligible closed-at-capture rows remained stable.
Any production treatment belongs to a separate future milestone; ID-5B
itself did not implement a runtime workaround.

## 8. Cross-track isolation with EMR — verified 2026-08-30

See `docs/ATHENA-EMR-HANDOFF.md` §8 for the full verification detail
(same finding, written from the other side). Summary: `grep`-confirmed
zero references to `explosive_move` anywhere in `src/athena/session/`,
`src/athena/intraday/`, or the two files this track's ID-5E/5F/5G/5G.1
milestones modified (`src/athena/data/store/repository.py`,
`src/athena/ops/owner_validation.py`); `grep`-confirmed EMR's own code
never calls any of the repository methods those milestones changed
(`list_candles_recent`, `get_latest_quote`, `get_latest_snapshot*`); the
two tracks write to separate database files (`db/athena.db` vs.
`db/emr.db`). The two tracks are architecturally isolated. The one shared
surface is `live_m5_provisional_settlement_diagnostic.py` — a neutral,
read-only, non-mutating data-layer utility (writes nothing to either
database) that happens to answer one real-world empirical question
relevant to both tracks' own separate downstream decisions. This is not a
code-coupling risk, but it does mean Monday's live captures for ID-5B and
EM-5's Track B should be coordinated (see §7) rather than run blind to
each other.

## 9. Required milestone closeout

Follow Design -> Implement -> Test -> Self-Validate -> Milestone Review
Summary -> owner review. Update `docs/MILESTONES.md`, this handoff,
`IMPLEMENTATION_SUMMARY.md`, and `ATHENA_BRIEFING.md` (if the module map
materially changes) in the same change set. Then stop and wait for owner
approval. Never begin the next milestone (including ID-6) automatically.

## 10. Worktree discipline

The worktree may contain owner or prior-agent changes (this session's own
ID-5E/5F/5G/5G.1 changes are already present — do not revert them). AI
never runs git actions (add/commit/push/etc.) unless the owner explicitly
requests it for that specific instance — provide a consolidated commit
message instead, per `CLAUDE.md`'s mandatory rule.

## 11. Continuation prompt

> Read `ATHENA_BRIEFING.md` and `docs/ATHENA-ID-TRACK-HANDOFF.md` first,
> then verify the Intraday Intelligence Track section in
> `docs/MILESTONES.md` and `docs/ATHENA-EMR-HANDOFF.md` §6/§8 for the
> shared-Monday-dependency context. ID-0 through ID-5G.1 are all
> owner-approved; ID-5 remains open for exactly one reason: ID-5B. If
> today is a real, live NSE trading day (verify via `date` — do not
> assume) and the owner has authorized it, proceed with ID-5B: Live
> Current-Session M5 Semantics Canary, using the frozen 5-instrument
> canary (benchmark index + 2 sector indexes + 2 equities) and the CASE
> A/B/C/D classification framework in this handoff's §7. Decide explicitly
> whether to reuse `live_m5_provisional_settlement_diagnostic.py`'s
> primitives directly or build a small ID-5-specific wrapper, and
> coordinate with whoever is running EMR's own EM-5 Track B capture the
> same morning before spending Kite request budget. Capture raw evidence
> only — no rounding/flooring/ceiling/nearest-match/resampling/
> normalization/forward-fill/synthesis, no repair or deletion of
> current-session rows, no runtime workaround in ORB/RS/RVOL. Do not begin
> ID-6 or any other milestone. Follow the milestone workflow, update all
> related ID-track docs, stop after the ID-5B Milestone Review Summary,
> and wait for owner approval.
