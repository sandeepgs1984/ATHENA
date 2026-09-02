# ATHENA Intraday Intelligence (ID-Track) Handoff

**Snapshot:** 2026-09-02 (ID-5B final settled-provider classification
owner-approved and CLOSED; ID-5 owner-approved and CLOSED; ID-6 discovery
architecture owner-approved with condition; ID-6A0 Entry Qualification ADR
owner-approved and closed; ID-6A owner-approved and closed; ID-6B.0
owner-approved and closed; ID-6B.1 owner-approved and closed; ID-6B.1A
owner-approved and closed, Option C ratified; ID-6B.1B owner-approved and
closed, v0 methodology frozen; ID-6B.2 pure engine owner-approved and
closed; ID-6B.2A input-coherence hardening owner-approved and closed —
ID-6B is fully closed; ID-6C persistence and ID-6C.1 canonical
Decision-binding hardening both owner-approved and closed — ID-6C is
fully closed; ID-6D workflow/Decision/finality resolution owner-accepted,
closure held for ID-6D.1; ID-6D.1 persistence-time semantics correction
implemented, ready for owner ID-6D closure review)
**Governing boundary:** accepted `docs/adr/ADR-013-entry-qualification-architecture.md`
for Entry Qualification; otherwise this track extends the existing frozen
`ATHENA-002-System-Blueprint.md` module map (§6 of `ATHENA_BRIEFING.md`).
**Current state:** ID-0 through ID-5G.1 are all owner-approved. ID-5B
(Live Current-Session M5 Semantics Canary) captured the **Monday
2026-08-31** frozen 5-instrument canary, ID-5B.1 corrected the
forming-vs-closed CASE classifier, and the owner approved the final
settled-provider classification `CASE_B_CONTENT_CHANGES` on 2026-09-01.
ID-5B is CLOSED and ID-5 is CLOSED. ID-6 discovery architecture is
owner-approved with condition, and ID-6A0 is owner-approved and closed after
ADR-013 acceptance on 2026-09-02. ID-6A domain/state/finality/confirmation
contracts are owner-approved and closed. ID-6B.0 methodology discovery is
owner-approved and closed. ID-6B.1 read-only evidence baseline is
owner-approved and closed — the baseline itself was accepted, but the
`EXPECTED_BAR_MISSING`=72.97% blocker was escalated to ID-6B.1A rather
than resolved. ID-6B.1A root-caused it to a chronic, unrepaired M15
candle off-grid condition (not a `SessionContext` defect — see §6 below),
re-ran the baseline uncapped (19x the original sample) to test
representativeness, and is owner-approved and closed with Option C
(artifact-owned availability) ratified in place of the blanket quality
gate. ID-6B.1B applied Option C correctly, audited the trend contract at
component level (confirming aggregate `BULLISH` already means genuine
M5+M15 agreement), and re-measured the candidate v0 policy over both the
original window and a fresh, deterministically-selected, materially wider
TRADE-representative window (10 sessions, 17,082 observations, 4.8x more
TRADE observations than the original). M15 was classified **NON-BLOCKING
TECHNICAL DEBT** (causes non-evaluability in <=0.03% of every sample
measured). WATCH and TRADE showed no structural divergence under the
quality-adjusted policy — single shared methodology preserved.
Recommendation: FREEZE V0 POLICY WITH EXPLICIT LIMITATION (checkpoint-level
flicker ~40% means point-in-time only, not persistence). The owner froze
the v0 methodology exactly as measured (VWAP positive AND aggregate trend
BULLISH AND (RS support OR RVOL support)) and ID-6B.1B is owner-approved
and closed. ID-6B.2 implemented the pure, deterministic
`EntryQualificationEngine` for that frozen methodology only —
`src/athena/intraday/entry_qualification_engine.py` — using an internal
tri-state AND/OR so missing evidence never collapses to bearish; state
precedence is non-WATCH/TRADE or non-trading-session → `OUT_OF_SCOPE`,
closed session → `EXPIRED`, pre-open → `NOT_YET`, regular session →
evaluate the frozen expression. `DISQUALIFIED_FOR_SESSION` is never
emitted; confirmation is always `NOT_EVALUATED`; `SessionDataQuality` is
never a blanket gate (Option C, test-proven); OR15/OR30/Gap/Sector proven
not to affect state. Owner review of ID-6B.2 accepted the methodology and
engine logic but held closure for one narrow, safety-critical gap:
`IntradaySignalSet` was never validated against `SessionContext`'s own
instrument/session-date/`as_of` identity, so a caller could in principle
supply evidence for the wrong instrument/checkpoint. ID-6B.2A closed that
gap with `_validate_input_coherence`/`_validate_nested_artifact_coherence`
(exact-equality checks, no tolerance, run unconditionally before any
methodology evaluation) — contract hardening only, the frozen methodology
itself is byte-for-byte unchanged and regression-tested. No persistence,
workflow stage, API, or UI has been implemented — ID-6C/ID-6D own those,
not yet started.
Evidence notes:
`docs/research/ID-5B-LIVE-M5-SEMANTICS-CAPTURE-2026-08-31.md`,
`docs/research/ID-6-SCOPE-ARCHITECTURE-DESIGN.md`,
`docs/research/ID-6B.1A-SESSION-DATA-QUALITY-AUDIT.md`, and
`docs/research/ID-6B.1B-QUALITY-ADJUSTED-POLICY-BASELINE.md`.

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
| ID-6 | DISCOVERY ARCHITECTURE OWNER APPROVED WITH CONDITION 2026-09-02 — corrected architecture accepted, condition satisfied by ID-6A0 approval; ID-6 remains active through its owner-gated slices |
| ID-6A0 | OWNER APPROVED / CLOSED 2026-09-02 — ADR-013 accepted after ID-6A0.1 corrected evidence finality/provenance vs methodology confirmation |
| ID-6A | OWNER APPROVED / CLOSED 2026-09-02 — immutable Entry Qualification domain contracts accepted; no engine, persistence, workflow, thresholds, ID-7, EM-6, EMR, DarvaX, or production behavior |
| ID-6B.0 | OWNER APPROVED / CLOSED 2026-09-02 — methodology/design accepted; illustrative practical-v0 rule not approved; owner decisions frozen for QUALIFIED allowed architecturally, terminal disqualification off in v0, OR contextual, WATCH/TRADE same methodology unless evidence proves otherwise, confirmation methodology unapproved, no additive score |
| ID-6B.1 | OWNER APPROVED / CLOSED 2026-09-02 — read-only settled historical market-time replay measured 370 candidate-checkpoint observations across 5 recent sessions and 32 instruments; `EXPECTED_BAR_MISSING`=72.97% blocker escalated to ID-6B.1A; no production engine implemented |
| ID-6B.1A | OWNER APPROVED / CLOSED 2026-09-02 — root-caused `EXPECTED_BAR_MISSING` to a chronic, unrepaired M15 off-grid data condition (96.30% of affected observations), confirmed zero M15 dependency in VWAP/RS/RVOL/Gap/OR by source inspection, verified checkpoint-boundary math exact (no harness/production bug), and re-ran the baseline uncapped (7,144 observations, 19x) finding every headline figure broadly stable except TRADE-specific ones (temporally concentrated on ~1 real day); Option C (artifact-owned availability) ratified over the blanket quality gate |
| ID-6B.1B | OWNER APPROVED / CLOSED 2026-09-02 — confirmed aggregate `BULLISH` trend already requires genuine M5+M15 agreement (source-level audit); applied Option C to the original window (99.55%-100% evaluable) and a fresh, deterministically-selected wider window (10 sessions, 2026-08-14–08-27, 17,082 observations, 4.8x more TRADE observations across 9 sessions, 99.64% evaluable); M15 caused non-evaluability in <=0.03% of every sample — classified NON-BLOCKING TECHNICAL DEBT; WATCH/TRADE showed a uniform prevalence shift with no structural divergence; owner froze v0 methodology exactly as measured (VWAP positive AND aggregate trend BULLISH AND (RS support OR RVOL support)) |
| ID-6B.2 | OWNER APPROVED / CLOSED 2026-09-02 — `EntryQualificationEngine.evaluate()` (`src/athena/intraday/entry_qualification_engine.py`): deterministic, side-effect-free, O(1), zero repository/provider/DB/wall-clock/workflow dependency; tri-state AND/OR so missing evidence never collapses to bearish; `DISQUALIFIED_FOR_SESSION` never emitted (exhaustive sweep test); confirmation always `NOT_EVALUATED`; `SessionDataQuality`/`EXPECTED_BAR_MISSING` never a blanket gate (Option C, test-proven); OR15/OR30/Gap/Sector proven not to affect state; WATCH/TRADE share one methodology; `evidence_finality` is an explicit orthogonal input, not inferred |
| ID-6B.2A | OWNER APPROVED / CLOSED 2026-09-02 — `_validate_input_coherence`/`_validate_nested_artifact_coherence`, called unconditionally before any branching in `evaluate()`. Requires exact equality (no tolerance) of instrument_id/session_date/as_of between `SessionContext` and `IntradaySignalSet`, plus the same for the two externally-supplied nested artifacts (`relative_strength`, `relative_volume`); `trend` needs no check (structurally guaranteed by `IntradayAnalyticsEngine.assess`'s own construction), `vwap` carries no identity fields. Mismatch raises `ValueError` deterministically, never `UNKNOWN`/`NOT_YET`. `Decision.instrument_id=None` fallback preserved, still coherence-checked. Option C/frozen methodology/WATCH-TRADE parity all regression-tested unchanged. Current/non-superseded Decision selection explicitly deferred to ID-6D, not solved here. 10 new focused tests (3 mutation-verified), 56/56 total. ID-6B (ID-6A through ID-6B.2A) is now fully closed |
| ID-6C | OWNER APPROVED / CLOSED 2026-09-02 — new `entry_qualifications` table (SCHEMA_VERSION 16→17), FK-bound to `decisions(decision_id)`, extending the existing `SqliteRepository`/`schema.py`/`serialization.py`. Append-only observations; composite primary key `(instrument_id, session_date, as_of, decision_id, methodology_version)` is the idempotency identity. `save_entry_qualification` idempotent on an identical repeat, fails loudly on a genuinely conflicting payload. Read API: `get_entry_qualification`, `latest_entry_qualification_for_decision`, `latest_entry_qualification_for_instrument_session`, `list_entry_qualifications_for_instrument_session` |
| ID-6C.1 | OWNER APPROVED / CLOSED 2026-09-02 — `_validate_entry_qualification_decision_binding` (`src/athena/data/store/repository.py`), runs on every `save_entry_qualification` call (both insert AND idempotency-check paths). Requires exact equality of `decision_type`/`run_id`/`cycle_id` with the referenced canonical Decision, and `instrument_id` only when `decision.instrument_id is not None` (mirrors `EntryQualificationEngine._resolve_instrument_id`'s own established fallback; confirmed real `DecisionEngine` always sets `instrument_id` for WATCH/TRADE). Missing decision_id → clean `RepositoryError` before any INSERT; schema FK remains as DB-level backstop (test-proven still enforced via bypass). Corrected run_id/cycle_id exclusion rationale: excluded from conflict comparison because binding validation already proved them equal to the Decision, not because they may differ. SCHEMA_VERSION unchanged (17). ID-6C is now fully closed |
| ID-6D | WORKFLOW/DECISION/FINALITY RESOLUTION OWNER-ACCEPTED; CLOSURE HELD FOR ID-6D.1 2026-09-02 — new `entry_qualification` `WorkflowStage` in `OwnerValidationPipeline` (depends on `decision` + `intraday_analytics`, declared last, order-stability proven). Current Decision = the Decision `dec_stage` just produced this same cycle (closure-captured, not re-queried) — provably freshest, no TTL invented. Engine called unconditionally; persistence scoped to WATCH/TRADE only. New pure `resolve_evidence_finality` (`src/athena/intraday/entry_qualification_provenance.py`) reuses the engine's own public structural/lifecycle eligibility gate (WATCH/TRADE AND `SessionPhase.REGULAR`) — never the tri-state formula — to resolve `LIVE_M5_PROVISIONAL` vs `UNKNOWN_PROVENANCE`; `NO_DECISIVE_PROVISIONAL_M5_DEPENDENCY` proven structurally unreachable (ADR-013's documented Decision-provenance insufficiency), reported honestly. Owner found `persisted_at=ctx.as_of` wrongly conflated evaluation time with write time — see ID-6D.1 |
| ID-6D.1 | IMPLEMENTED — READY FOR OWNER ID-6D CLOSURE REVIEW 2026-09-02 — added injectable `OwnerValidationPipeline(..., persistence_clock: Callable[[], datetime] | None = None)`, defaulting to `datetime.now(tz=timezone.utc)` (audited first: no existing injectable wall-clock abstraction; found the established `utc_now()`/inline `datetime.now(tz=UTC)` convention plus `SqliteRepository.set_ops_meta`'s own optional-timestamp precedent). Stage now calls `persisted_at=self._persistence_clock()`, never `ctx.as_of`. Proved with genuinely distinct injected values: `as_of` unchanged from `SessionContext`, `persisted_at` correctly distinct and timezone-aware (verified via direct SQL, since the domain object doesn't expose write metadata); idempotent retry preserves the original `persisted_at` across two full pipeline executions with different clock values; latest-query ordering reconfirmed `as_of`-only (proven with `as_of`/`persisted_at` in deliberately opposite order). Pure engine remains structurally clock-free. SCHEMA_VERSION unchanged (17). 4 new focused tests, 1 mutation-verified. Full suite 3,131 passed. No methodology/Decision-selection/finality/schema/API/UI change |

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

## 6. ID-6 / ID-6B — current architecture gate

ID-6 discovery/design is complete and hardened as of 2026-09-02:
`docs/research/ID-6-SCOPE-ARCHITECTURE-DESIGN.md`.

Owner review decision: ID-6 discovery architecture is owner-approved with
condition, and the required ID-6A0 condition is now satisfied. ADR-013
(`docs/adr/ADR-013-entry-qualification-architecture.md`) is owner-approved /
accepted as of 2026-09-02.

The approved architecture treats current-session completed M5 as provisional
for qualification purposes after ID-5B's accepted
`CASE_B_CONTENT_CHANGES` result; state, evidence finality/provenance, and
qualification confirmation are orthogonal; and no
irreversible ID-6 state may be caused directly or indirectly solely by
live-M5-provisional evidence.

ID-6A implements only the immutable domain/state/finality/confirmation
contracts under `src/athena/intraday/entry_qualification_models.py` and is
owner-approved / closed as of 2026-09-02.

ID-6B.1 is owner-approved and closed:
`docs/research/ID-6B.1-ENTRY-QUALIFICATION-EVIDENCE-BASELINE.md` records the
read-only evidence baseline. The baseline artifacts live under
`artifacts/research/id6b1/`; stable analysis SHA-256 is
`7baf33e01df22d2acae000c44bcb7b0be0f2017d12248432e435eb986619b5fb`. The
baseline itself was accepted, but its `EXPECTED_BAR_MISSING`=72.97%
finding was escalated to ID-6B.1A rather than resolved.

ID-6B.1A is owner-approved and closed:
`docs/research/ID-6B.1A-SESSION-DATA-QUALITY-AUDIT.md`. Root cause: a
chronic, systemic M15 candle off-grid condition in `db/athena.db` — only
a session's own opening M15 bar (`09:15:00`) is reliably on-grid; every
subsequent M15 row is off-grid by seconds to tens of minutes (confirmed
directly against the real database). `live_m5_settlement_repair.py` is
hardcoded to `Timeframe.M5` — no M15 equivalent exists anywhere in the
repository, so unlike M5 (repaired for settled dates by ID-5A), M15 has
never been repaired. This is **not a `SessionContext` code defect** — its
completion logic correctly reports the missing bars; the underlying M15
data itself is the gap. Confirmed by direct source inspection that VWAP,
`RelativeStrengthContext`, `RelativeVolumeContext`, `GapContext`, and
`OpeningRangeEvidence` have **zero M15 dependency** — only the trend
label's 15m leg touches M15, under a materially looser contract than
`SessionContext`'s own blanket gate. Checkpoint-boundary math was
independently re-verified exact (no off-by-one, no harness bug). A
19x-larger uncapped replay (7,144 observations, same 5 sessions/6
checkpoints, artifacts under `artifacts/research/id6b1a/uncapped_baseline/`,
SHA-256 `bee4626fb0d418db2643bce0d286a6500b080f1bc21e11fd124cfa1fd7014491`)
found every headline prevalence figure broadly stable except TRADE-
specific figures, which remain provisional because TRADE decisions in
this window are concentrated on effectively one real trading day.
Recommendation: GO WITH CONDITIONS — adopt artifact-owned availability
(Option C) instead of the blanket `SessionDataQuality` gate; document the
M15 data gap as a future, separately-authorized prerequisite candidate
(mirroring ID-5A), not fixed here. The owner ratified Option C and
authorized ID-6B.1B.

ID-6B.1B is owner-approved and closed:
`docs/research/ID-6B.1B-QUALITY-ADJUSTED-POLICY-BASELINE.md`. First audited
the intraday trend contract at source level (`_aggregate_trend` in
`src/athena/intraday/engine.py`) and confirmed the existing aggregate
`BULLISH` label already requires genuine M5+M15 agreement — ID-6B.1's own
`candidate_policy_match` measurement needed no formula correction. Defined a
research-only `EVALUABLE_FOR_CANDIDATE_POLICY` contract (VWAP + M5 trend +
M15 trend + RS-or-RVOL, each independently available) and re-analyzed
ID-6B.1's own existing observation files directly (no replay needed):
100.00% evaluable (370-obs sample) and 99.55% evaluable (7,144-obs sample),
with M15 causing non-evaluability in only 2 of 7,144 observations (0.03%).

Surveyed real `decisions` table counts across all 24 available trading
dates and found TRADE decisions exist on 20 consecutive sessions
(2026-07-31–08-27) but zero on the 4 most recent — explaining why ID-6B.1's
original window barely captured TRADE. Selected the 10 most recent
consecutive TRADE-bearing sessions preceding ID-6B.1's own window
(2026-08-14–08-27) as the deterministic wider window (selection rule
reported before any policy-match analysis), then replayed it uncapped via
ID-6B.1's own unmodified harness: 17,082 observations (artifacts under
`artifacts/research/id6b1b/wider_window/`, gitignored), 418.469s runtime,
7,134 TRADE observations across 9 of 10 sessions (4.8x ID-6B.1's original
TRADE count). Quality-adjusted re-analysis: 99.64% evaluable; M15 caused
non-evaluability in only 4 of 17,082 observations (0.02%) — **classified
NON-BLOCKING TECHNICAL DEBT**, not a prerequisite for a future Entry
Qualification engine. WATCH vs. TRADE showed a uniform prevalence shift
(TRADE a few points higher on every named field) with no structural
divergence — the existing single-shared-methodology decision stands.
Checkpoint-level flicker re-measured at 39.76% (wider window), consistent
in order of magnitude with the same-window figure (46.43%) — confirms
flicker is real and stable across sample sizes, reinforcing the deferral of
`CONFIRMED_BY_POLICY`.

Recommendation: **FREEZE V0 POLICY WITH EXPLICIT LIMITATION** — the policy
is coherent, almost always evaluable, and stable in prevalence, but
checkpoint-level flicker means it must be treated as a point-in-time signal
only, never a persistence/confirmation signal. The owner froze the v0
methodology exactly as measured — `VWAP positive AND aggregate trend
BULLISH AND (RS support OR RVOL support)` — and authorized ID-6B.2 to
implement the pure engine only, with two corrections to ID-6B.1B's own
§18 engine-semantics proposal: `EXPIRED` means session-lifecycle-ended
(not a reserved future rule), and v0 confirmation uses the existing ID-6A
`NOT_EVALUATED` value (not a proposed new one).

ID-6B.2's methodology and engine logic are owner-accepted:
`src/athena/intraday/entry_qualification_engine.py`
(`EntryQualificationEngine`). Deterministic, side-effect-free, O(1) pure
engine implementing only the frozen v0 expression, via an internal
tri-state (`TRUE`/`FALSE`/`UNKNOWN`) AND/OR helper so missing evidence
never silently collapses to false through Python truthiness: AND lets
FALSE dominate UNKNOWN, OR lets TRUE dominate UNKNOWN. State precedence:
non-WATCH/TRADE decision type or `SessionPhase.NOT_A_TRADING_SESSION` →
`OUT_OF_SCOPE`; `SessionPhase.CLOSED` → `EXPIRED`; `SessionPhase.PRE_OPEN`
→ `NOT_YET` (no clock constant invented); `SessionPhase.REGULAR` →
evaluate the frozen expression → `QUALIFIED`/`NOT_YET`/`UNKNOWN`.
`DISQUALIFIED_FOR_SESSION` is never emitted (proven by an exhaustive
phase x leg-combination sweep test). Confirmation is always
`EntryQualificationConfirmation.NOT_EVALUATED`; `CONFIRMED_BY_POLICY` is
never emitted. `SessionContext.data_quality`/`IntradaySignalSet.data_quality`
are never read as a blanket gate (Option C — test-proven that
`EXPECTED_BAR_MISSING` does not block `QUALIFIED`). OR15/OR30/Gap/Sector
Health are proven by test not to influence state. WATCH and TRADE share one
evaluation path, canonical `decision_type`/`decision_id` preserved, never
mutated/promoted. `evidence_finality` (ADR-013's second orthogonal
dimension) is an explicit, required caller input, echoed through unchanged
— the engine does not infer provenance from a bare `Decision` (ID-6B.1B/
ADR-013 already established current `Decision` provenance is insufficient
for that); resolving it from real data is deferred to ID-6C/ID-6D.
`EntryQualificationReasonCode` (ID-6A) was extended minimally, additively,
with 10 new v0-methodology reason codes.

46 new focused tests (`tests/market_intel/test_entry_qualification_engine.py`),
all non-vacuous; the two most safety-critical (tri-state FALSE-dominates-
UNKNOWN, and the Option C non-gate) were independently confirmed by
deliberately mutating the engine logic, observing the expected test
failure, and reverting.

Owner review of ID-6B.2 found one safety-critical gap and held closure for
it: the engine validated `Decision` vs. `SessionContext` instrument
coherence, but never proved the supplied `IntradaySignalSet` belonged to
the same instrument, session date, and evaluation checkpoint (`as_of`) as
the `SessionContext` being evaluated. ID-6B.2A closed that gap: added
`_validate_input_coherence`/`_validate_nested_artifact_coherence`,
called unconditionally at the top of `evaluate()` before any branching.
Requires exact equality (no tolerance — source-audited to be the real
production contract every existing caller already follows) of instrument/
session-date/`as_of` between `SessionContext` and `IntradaySignalSet`, plus
the same three checks against the two v0-consumed nested artifacts built by
separate engines (`relative_strength`, `relative_volume`). `trend` needs no
separate check (`IntradayAnalyticsEngine.assess` always builds it from the
same local variables as the top-level `IntradaySignalSet`, source-verified
to make divergence structurally unreachable); `vwap` carries no identity
fields. A mismatch raises `ValueError` deterministically — never `UNKNOWN`/
`NOT_YET`, since a contract violation is a programmer/caller error, not a
market state. `Decision.instrument_id=None`'s existing fallback is
preserved and still coherence-checked (no loophole). Current/non-superseded
`Decision` selection is explicitly documented as a caller/workflow
responsibility deferred to ID-6D — the pure engine has no repository access
and cannot resolve it, and ID-6B.2A does not attempt to.

10 new focused tests, all non-vacuous, 3 of the most safety-critical
(top-level instrument check and both nested-artifact checks) independently
confirmed by deliberately disabling each check, observing the expected test
failure, and reverting — combined total 56/56 passing. ID-6B (ID-6A through
ID-6B.2A) is now **owner-approved and fully closed** — the v0 methodology
and pure engine are frozen; do not reopen the readiness formula, tri-state
logic, state precedence, Option C, WATCH/TRADE parity, confirmation
semantics, evidence-finality semantics, point-in-time behavior, or
input-coherence rules.

ID-6C's persistence architecture is owner-approved and closed: `src/athena/data/store/schema.py`
(new `entry_qualifications` table, SCHEMA_VERSION 16→17, FK-bound to
`decisions(decision_id)`), `serialization.py`, and `repository.py`
(`SqliteRepository.save_entry_qualification`/`get_entry_qualification`/
`latest_entry_qualification_for_decision`/
`latest_entry_qualification_for_instrument_session`/
`list_entry_qualifications_for_instrument_session`). Persists exactly what
the closed ID-6B.2/2A engine concludes — no methodology reinterpretation.
Append-only: `EntryQualification` is point-in-time/non-sticky (ID-6B
measured ~40% checkpoint flicker), so a later observation for the same
instrument/session is a new row, never an overwrite. The composite primary
key `(instrument_id, session_date, as_of, decision_id, methodology_version)`
is the logical/idempotency identity — `run_id`/`cycle_id` are not part of
it, since `decision_id` already functionally determines them. No
point-in-time (`as_of<=requested`) query was added (no current need
justifies it; likely ID-6E). Design note: `docs/design/ID-6C-ENTRY-QUALIFICATION-PERSISTENCE.md`.

Owner review found one integrity gap and held closure for it: a foreign
key on `decision_id` alone only proves the referenced Decision *exists* —
it never proved the persisted `EntryQualification`'s own Decision-derived
fields (`instrument_id`, `decision_type`, `run_id`, `cycle_id`) actually
agreed with it, so a row could in principle claim a different instrument
or `decision_type` than its bound Decision. ID-6C.1 closed that gap: added
`_validate_entry_qualification_decision_binding`,
which loads the canonical Decision by `eq.decision_id` and requires exact
equality of `decision_type`/`run_id`/`cycle_id`, and `instrument_id` only
when `decision.instrument_id is not None` — mirroring
`EntryQualificationEngine._resolve_instrument_id`'s own established
fallback exactly (source-confirmed: the real production `DecisionEngine`
always sets `instrument_id` for WATCH/TRADE Decisions, so that branch is a
defensive completeness path, not an exercised real one). This check runs
on **every** `save_entry_qualification` call — both insert and
idempotency-check paths — so an already-persisted valid row can never let
a second, Decision-inconsistent call hide behind "identical identity ⇒
no-op" (this was a real gap: since `run_id`/`cycle_id` were already
excluded from the conflict-payload comparison, a same-`decision_id`-
different-`run_id` write would previously have returned a false idempotent
`False`). A missing `decision_id` now raises a clean repository-level
`RepositoryError` before any INSERT; the schema FK remains as a DB-level
backstop, test-proven still enforced by bypassing the repository method.
`run_id`/`cycle_id` remain excluded from the payload conflict comparison —
corrected rationale: not because they may legitimately differ, but because
binding validation has already proven them equal to the canonical
Decision by the time that comparison runs. SCHEMA_VERSION unchanged (17) —
repository-level validation was sufficient, no DDL change.

Combined 40 focused tests (replaced 1 stale test whose expectation was now
wrong, added 10 — net +7), all non-vacuous. 2 of the most safety-critical
(the `run_id` binding check itself, and separately the *ordering*
requirement that binding validation runs before, not after, the
idempotency check) independently mutation-verified. ID-6C (including
ID-6C.1) is now **owner-approved and fully closed** — the persistence
architecture, identity key, idempotency, conflict detection, and Decision
binding are frozen; do not reopen them.

ID-6D's workflow placement, current-Decision resolution, and evidence-
finality resolution are owner-accepted: the closed Entry Qualification
chain is wired into the canonical runtime for the first time. A new
`entry_qualification` `WorkflowStage` was added to
`OwnerValidationPipeline._scan_eligible`'s per-instrument graph
(`src/athena/ops/owner_validation.py`), depending on `decision` and
`intraday_analytics` — the first stage to join those two previously-
independent branches, declared last so it cannot perturb the ten
pre-existing stages' relative order (proven against the real topological
sort; the existing 44-test `test_owner_validation.py` suite passes
unmodified). "Current Decision" is defined as exactly the Decision
`dec_stage` just produced this same synchronous cycle (closure-captured
via the existing `box["cap"]`, never a fresh repository query) — provably
the freshest possible artifact given the single-threaded, sequential
per-instrument execution model, so no TTL/age heuristic was invented. The
engine is called unconditionally (it already self-handles non-WATCH/TRADE
via `OUT_OF_SCOPE`); persistence is scoped to WATCH/TRADE only, per the
owner's explicit "do not flood persistence" instruction.

The milestone's primary design task — evidence-finality resolution — is
implemented as a new pure function, `resolve_evidence_finality`
(`src/athena/intraday/entry_qualification_provenance.py`). Source-audited
that all four direct readiness families (VWAP, aggregate trend's M5/M15
legs, RS, RVOL) are M5/M15-derived, and that `live_m5_settlement_repair.py`
itself excludes "today's still-open/most-recent session" from repair. The
resolver reuses the pure engine's own *public structural/lifecycle
eligibility gate* (`decision_type` WATCH/TRADE AND `SessionPhase.REGULAR`)
— never the inner tri-state formula — as the sole signal for direct
M5-dependence, computed *before* the engine runs (finality is a required
input, so reason-code introspection would need a second invocation).
Result: `LIVE_M5_PROVISIONAL` whenever REGULAR-phase evaluation will
occur; `UNKNOWN_PROVENANCE` otherwise, deferring to indirect canonical-
Decision provenance, which ADR-013/ID-6B.0 already established cannot
currently be positively proven (no `DecisionEngine` retrofit was
attempted). `NO_DECISIVE_PROVISIONAL_M5_DEPENDENCY` is **structurally
unreachable** under the current runtime — proven exhaustively across every
`DecisionType` x `SessionPhase` combination by a dedicated test, reported
honestly rather than faked, exactly as the owner's own instruction
anticipated. A known, documented conservatism limitation: the
`SessionPhase.REGULAR` signal is relative to the supplied `as_of`, not
true wall-clock "now" — a historical replay could also classify as
`LIVE_M5_PROVISIONAL` even if that session's M5 has since settled, a
deliberately safe over-classification, never under.

A real, temp-DB integration test proves the whole chain end-to-end against
seeded market data: exact Decision binding (satisfying ID-6C.1's own
invariant), correct `as_of` (from `SessionContext`, never wall-clock),
idempotent re-run (one persisted row after two identical full-pipeline
executions with the same `run_id`), and object-identity reuse of
`SessionContext`/`IntradaySignalSet` (no duplicate construction). 13 tests
(9 resolver + 4 workflow-integration), 2 mutation-verified.

Owner review held ID-6D closure for one defect: the original
implementation set `persisted_at=ctx.as_of`, wrongly conflating the
evaluation/market-time checkpoint with the actual durable-write instant —
two intentionally independent dimensions that diverge under delayed
execution, retry, recovery, queued processing, historical replay, or
reprocessing. **ID-6D.1 closed that gap**: audited existing clock
conventions first (no injectable wall-clock abstraction existed anywhere;
found the established per-module `utc_now()`/`_utc_now()`/inline
`datetime.now(tz=UTC)` convention in `portfolio/sync.py`/
`darvax/screening/sweep.py`/`explosive_move/store/repository.py`, plus
`SqliteRepository.set_ops_meta`'s own optional-injectable-timestamp
precedent on the very class `save_entry_qualification` belongs to).
`save_entry_qualification`'s own `persisted_at` parameter was already
correctly designed since ID-6C — the defect was entirely in the caller.
Added an injectable `OwnerValidationPipeline(..., persistence_clock:
Callable[[], datetime] | None = None)`, defaulting to `datetime.now(tz=timezone.utc)`;
the stage now calls `persisted_at=self._persistence_clock()`, never
`ctx.as_of`, never a bare inline `datetime.now()`. `EntryQualificationEngine`
and every other pure engine remain structurally clock-free.

Proved with genuinely distinct injected values: `as_of` unchanged from
`SessionContext`; the stored `persisted_at` (verified via direct SQL,
since the domain object doesn't expose write metadata) is correctly
distinct and timezone-aware; idempotent retry preserves the **original**
`persisted_at` across two full pipeline executions with two different
injected clock values (the later retry's write-time attempt is
discarded); latest-lookup ordering reconfirmed strictly `as_of`-based —
with `as_of`/`persisted_at` deliberately given *opposite* relative order
to prove the query isn't secretly keying off write time. SCHEMA_VERSION
unchanged (17) — `persisted_at` already existed as a column since ID-6C,
no DDL needed.

4 new focused tests, all non-vacuous, 1 mutation-verified (reverting to
`persisted_at=ctx.as_of` correctly failed both the distinct-timestamp and
idempotent-retry tests; reverted and reconfirmed clean). Full repository
suite: 3,131 passed, 1 pre-existing skip. No production DB writes during
development (`db/athena.db` untouched — confirmed no reference to its
real path anywhere in changed code/tests), no methodology/Decision-
selection/finality-resolver/schema change, no API/UI. Design note:
`docs/design/ID-6D-ENTRY-QUALIFICATION-WORKFLOW-INTEGRATION.md` (§9/§12
corrected).

Do not add API/UI, thresholds, IntradayTradePlan, an M15 settlement-repair
milestone, ID-6E, ID-7, EM-6, EMR, DarvaX, or order behavior until the
owner reviews the ID-6D.1 persistence-time correction and closes ID-6D.

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
