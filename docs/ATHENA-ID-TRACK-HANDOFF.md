# ATHENA Intraday Intelligence (ID-Track) Handoff

**Snapshot:** 2026-09-03 (ID-5B final settled-provider classification
owner-approved and CLOSED; ID-5 owner-approved and CLOSED; ID-6 discovery
architecture owner-approved with condition; ID-6A0 Entry Qualification ADR
owner-approved and closed; ID-6A owner-approved and closed; ID-6B.0
owner-approved and closed; ID-6B.1 owner-approved and closed; ID-6B.1A
owner-approved and closed, Option C ratified; ID-6B.1B owner-approved and
closed, v0 methodology frozen; ID-6B.2 pure engine owner-approved and
closed; ID-6B.2A input-coherence hardening owner-approved and closed —
ID-6B is fully closed; ID-6C persistence and ID-6C.1 canonical
Decision-binding hardening both owner-approved and closed — ID-6C is
fully closed; ID-6D workflow/Decision/finality resolution and ID-6D.1
persistence-time semantics correction are both owner-approved and closed —
ID-6D is fully closed; ID-6E.1, ID-6E.2, and ID-6E.3 are all owner-approved
and closed — historical replay validation classified BEHAVIORALLY SOUND;
production schema activation and runtime persistence canary both closed,
shadow accumulation active; the first genuine REGULAR-phase shadow
evidence (489 rows, 2 checkpoints) found and characterized with zero
integrity defects across 654 audited rows. **Closure gate clarified
(2026-09-03, documentation only):** production issues a fresh canonical
Decision per instrument per cycle (confirmed from real `decision_id`
values), so same-Decision multi-checkpoint episodes are architecturally
not expected and are no longer a closure requirement; TRADE observation
and a second session remain desirable but not mandatory; the sole
remaining gate is breadth of later-session REGULAR checkpoints beyond the
09:15/09:30 pair ID-6E.3 already characterized. **Final post-market audit
completed 2026-09-03** after the full trading session closed (6,640 rows,
28 checkpoints, entire session bounded population): all invariants hold
exactly, 0 binding/integrity defects, later-session UNKNOWN confirmed
bounded/explainable, same-Decision multi-checkpoint episodes still 0 (now
confirmed architectural, not a gap), deterministic, 0 mutation.
Classification **`REPLAY_AND_SHADOW_BEHAVIORALLY_SOUND`**. **Owner
reviewed and accepted this audit 2026-09-03: ID-6E OWNER APPROVED /
CLOSED, and ID-6 OVERALL OWNER APPROVED / CLOSED (entire track, ID-6A0
through ID-6E) — see §6 below.** **ID-7 discovery (2026-09-03):**
owner-authorized discovery-only turn found current `TradePlan` is
daily/ATR-only with zero intraday-evidence inputs and cannot be
retrofitted to consume `EntryQualification` (structural violations);
recommends a new, separate intraday actionability artifact
(`docs/research/ID-7-INTRADAY-ENTRY-TRADEPLAN-DISCOVERY.md`) and a new
ADR — **owner approved the discovery and accepted Option B as the
architectural direction 2026-09-03; ID-7A0 not started.** ID-6 closure
does not by itself authorize implementation. **ID-7P0 (2026-09-03):**
owner-authorized latency-attribution instrumentation (opt-in, orthogonal
wall-clock timing, never touching `WorkflowEngine`'s own deterministic
clock) implemented, tested, and wired into the real scheduled path, then
deployed via an **owner-authorized production restart (2026-09-03,
safety-verified — no active cycle interrupted, zero artificial runs/
provider calls/Decisions/EntryQualification rows created)** — a provider
rate-limit audit found a real pacing floor accounting for **≈95.8%** of
the observed average latency (corrected 2026-09-03 by ID-7P0.1 from an
initial, unverified ≈63% estimate — see below), strong prior evidence for
`INGESTION_DOMINANT`, pending actual measured natural-cycle evidence.
Tested: 3,259 passed. Status: **ID-7P0 INSTRUMENTATION LIVE — NATURAL
EVIDENCE ACCUMULATION ACTIVE**, next expected 2026-09-04. Full detail:
`docs/research/ID-7P0-PRODUCTION-CYCLE-LATENCY-ATTRIBUTION.md`)
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
| ID-6D | OWNER APPROVED / CLOSED 2026-09-02 — new `entry_qualification` `WorkflowStage` in `OwnerValidationPipeline` (depends on `decision` + `intraday_analytics`, declared last, order-stability proven). Current Decision = the Decision `dec_stage` just produced this same cycle (closure-captured, not re-queried) — provably freshest, no TTL invented. Engine called unconditionally; persistence scoped to WATCH/TRADE only. New pure `resolve_evidence_finality` (`src/athena/intraday/entry_qualification_provenance.py`) reuses the engine's own public structural/lifecycle eligibility gate (WATCH/TRADE AND `SessionPhase.REGULAR`) — never the tri-state formula — to resolve `LIVE_M5_PROVISIONAL` vs `UNKNOWN_PROVENANCE`; `NO_DECISIVE_PROVISIONAL_M5_DEPENDENCY` proven structurally unreachable (ADR-013's documented Decision-provenance insufficiency), reported honestly. Owner found `persisted_at=ctx.as_of` wrongly conflated evaluation time with write time — corrected by ID-6D.1. ID-6D (including ID-6D.1) is now fully closed |
| ID-6D.1 | OWNER APPROVED / CLOSED 2026-09-02 — added injectable `OwnerValidationPipeline(..., persistence_clock: Callable[[], datetime] | None = None)`, defaulting to `datetime.now(tz=timezone.utc)` (audited first: no existing injectable wall-clock abstraction; found the established `utc_now()`/inline `datetime.now(tz=UTC)` convention plus `SqliteRepository.set_ops_meta`'s own optional-timestamp precedent). Stage now calls `persisted_at=self._persistence_clock()`, never `ctx.as_of`. Proved with genuinely distinct injected values: `as_of` unchanged from `SessionContext`, `persisted_at` correctly distinct and timezone-aware (verified via direct SQL, since the domain object doesn't expose write metadata); idempotent retry preserves the original `persisted_at` across two full pipeline executions with different clock values; latest-query ordering reconfirmed `as_of`-only (proven with `as_of`/`persisted_at` in deliberately opposite order). Pure engine remains structurally clock-free. SCHEMA_VERSION unchanged (17). 4 new focused tests, 1 mutation-verified. Full suite 3,131 passed. No methodology/Decision-selection/finality/schema/API/UI change |
| ID-6E | OWNER APPROVED / CLOSED 2026-09-03 — FINAL CLASSIFICATION `REPLAY_AND_SHADOW_BEHAVIORALLY_SOUND` — validation-only milestone: deterministic historical market-time replay via the real, unmodified `EntryQualificationEngine`/`resolve_evidence_finality`, plus read-only inspection of persisted shadow observations in real `db/athena.db`. New harness `src/athena/data/id6e_replay_shadow_validation.py` reuses ID-6B.1's `ReadOnlyStore`/`candidates_at` and ID-6B.1B's exact 10-session/17,082-observation window; two independent full replay runs produced a byte-identical SHA-256 digest (full determinism, zero provider calls). Every point-observation headline statistic matches ID-6B.1B's own research figures almost exactly (QUALIFIED 21.70%, TRADE 24.17%, WATCH 19.93%) with zero tuning. All frozen invariants hold across all 17,082 observations, Option C and M15 non-blocking status reconfirmed at full scale. Owner accepted the historical replay validation as **BEHAVIORALLY SOUND** after ID-6E.1's Decision-episode trajectory correction. Shadow validation progressed through ID-6E.2 (schema activation)/ID-6E.3 (first genuine REGULAR characterization), then a final read-only post-market audit (2026-09-03, 6,640 rows across the full completed session, §53 of the research doc) found all invariants hold exactly, 0 defects of any kind, and classified **`REPLAY_AND_SHADOW_BEHAVIORALLY_SOUND`** — owner reviewed and accepted this audit 2026-09-03: **ID-6E OWNER APPROVED / CLOSED** |
| ID-6E.1 | OWNER APPROVED / CLOSED 2026-09-02 — corrected `_transitions`/`_qualified_duration` to group by canonical `(instrument_id, session_date, decision_id)` instead of `(instrument_id, session_date, decision_type)`, ordered by semantic `as_of` instead of the checkpoint label. Added a new descriptive `_decision_supersession` audit: 3,210 of 3,401 instrument/session groups (94.4%) contain more than one distinct Decision episode across the 6 replay checkpoints — Decision churn is the norm in this population. Corrected flicker: 215 of 1,833 multi-checkpoint Decision episodes = **11.73%** (was 39.76% under the old, over-merged grouping) — the prior figure is superseded, root-caused, and documented, not silently left in the narrative. Audited ID-6B.1B's own harness and confirmed it shares the identical `decision_type`-grouping defect, predating ID-6E entirely (research-only contract written before ID-6C's Decision-binding persistence discipline existed) — ID-6B.1B's own artifacts were not modified. All point-observation invariants confirmed byte-for-byte unchanged; new deterministic digest (`d18c2cb1c43688804c7aea8430b1d4a1539c48f4b3cab3e2a05fd2bba8a70ef9`) matches exactly across two independent reruns of the real 17,082-observation replay against `db/athena.db`. 5 new focused tests (2 mutation-verified), 23/23 `test_id6e_replay_shadow_validation.py` passing, combined ID-6A–ID-6E suite 194 passed, full suite 3,154 passed, 1 pre-existing skip. No methodology/engine/workflow/repository/schema/API/UI change |
| ID-6E.2 | OWNER APPROVED / CLOSED 2026-09-03 — operational-only milestone (no methodology/engine/workflow/schema code change). Preflight against real `db/athena.db` found SCHEMA_VERSION already 17 with `entry_qualifications` present (0 rows) — migration had already occurred via ATHENA's own routine, idempotent `SqliteRepository.initialize()` calls (`_open_repo()`/API startup); no ad-hoc SQL issued anywhere. Integrity-verified, checksummed safety backup taken (`db/backups/athena-pre-id6e2-shadow-canary-20260903T024201Z.db`). Structural verification against a fresh v17 reference schema: 0 drift (28/28 tables, 56/56 indexes, exact `entry_qualifications` column/PK/FK/index match). Idempotency reconfirmed via an explicit second `initialize()` call. The already-running, already-scheduled production server fired its own PREMARKET cycle (08:15:29 IST) on its own schedule — no manual trigger — persisting **165 genuine `EntryQualification` rows** through the normal `OwnerValidationPipeline` runtime path. Full-population integrity audit: 0 defects of any kind across all 165 rows. All rows are `EXPIRED`/`UNKNOWN_PROVENANCE`/WATCH — read-only root-caused to the cycle's 08:15 `as_of` falling before `preopen_start` (09:00), correctly classified `SessionPhase.CLOSED` by the frozen, untouched session engine — verified as correct, by-design behavior, not a defect. Owner approved: production schema activation CLOSED, runtime persistence canary CLOSED, shadow accumulation ACTIVE. Full record: `docs/ops/ID-6E2-ENTRY-QUALIFICATION-PRODUCTION-SCHEMA-ACTIVATION.md`. Full repository suite 3,190 passed, 1 pre-existing skip |
| ID-6E.3 | OWNER APPROVED / CLOSED 2026-09-03 — read-only characterization only (no production writes, no scheduler trigger, no config/methodology/runtime change). Fixed a deterministic audit cutoff (`persisted_at<=2026-09-03T04:09:59Z`, 654 rows) so the continuously-accumulating live table couldn't make the report internally inconsistent (grew to 893 rows by report time — not analyzed). Reconstructed canonical `SessionPhase` for all 3 distinct `as_of` values via the frozen, unmodified `classify_session_phase`: 08:15 CLOSED (165 rows, unchanged), 09:15/09:30 **REGULAR** (489 rows — first genuine REGULAR-phase shadow evidence). REGULAR finality invariant holds exactly (489/489 `LIVE_M5_PROVISIONAL`); state distribution NOT_YET 65.44%/UNKNOWN 19.02%/QUALIFIED 15.54%. UNKNOWN concentrated at the literal open (33.7% at 09:15, dropping to 3.0% by 09:30) — VWAP needs a completed M5 bar, a genuine live-market artifact, not a defect. Full-population integrity audit (654 rows): **zero defects of any kind**. Canonical `(instrument_id, session_date, decision_id)` trajectory grouping (never `decision_type`) found **0 multi-checkpoint Decision episodes** (89.5% Decision churn across just 2 checkpoints) — genuine shadow flicker **not yet measurable**, reported as a real gap, not forced. 0 TRADE observations anywhere. Option C not reconstructable from persisted evidence (data_quality not stored) — reported honestly. Root causes (NOT_YET: trend/VWAP dominate; QUALIFIED: 4 structural reason codes) directionally match replay. Persistence latency (~550-559s) consistent across all 3 cycles regardless of type. Checkpoint-matched replay comparison (shadow 09:30 vs. replay 09:30) is closer than a blended aggregate. Classification: **REPLAY_SOUND_SHADOW_EVIDENCE_STILL_ACCUMULATING** — contract correctness strongly supported; trajectory/flicker and TRADE-type characterization not yet supported. No source changed; full repository suite 3,190 passed, 1 pre-existing skip. Owner approved ID-6E.3 and directed: allow normal production shadow accumulation, no new implementation milestone, no artificial evidence-diversity forcing (0 TRADE / 0 multi-checkpoint episodes accepted as genuine, not a defect); next read-only review only once evidence materially changes. **ID-6E overall remains OPEN** |
| ID-7 | ✅ DISCOVERY OWNER APPROVED / CLOSED 2026-09-03 — OPTION B ACCEPTED, ID-7A0 NOT STARTED — owner-authorized discovery-only turn (no production source touched). Current `TradePlan` confirmed daily-only/ATR-multiple (`entry=last_close`, `stop=last_close±1.5×ATR(D1)`, `target=last_close±3.0×ATR(D1)`, R:R fixed 2.0), embedded inside immutable `Decision` with no independent identity/table, TRADE-type-only, zero intraday-evidence inputs, structurally unable to consume `EntryQualification` (which is downstream/consumer-only of the already-finalized Decision). New finding: `entry_qualification` writes cluster in the final ~5-7s of each ~550-560s cycle — the ~9-10 min latency is spent almost entirely before the scan loop, most plausibly in sequential non-batched ingestion (circumstantial, no direct stage instrumentation exists at the time). Recommended a new, separate `(decision_id, entry_qualification identity)`-bound intraday actionability artifact orthogonal to TradePlan (Option B), a new ADR (matches ADR-013's own stated trigger criteria), and an ID-7A0→ID-7F sequence mirroring ID-6's. 5 owner policy questions raised. Full detail: `docs/research/ID-7-INTRADAY-ENTRY-TRADEPLAN-DISCOVERY.md`. **Owner accepted Option B as the architectural direction, required TradePlan-independent naming for the future artifact (exact name deferred to ID-7A0), and authorized ID-7P0 to replace the latency hypothesis with measured evidence before ADR drafting.** No ADR drafted, no ID-7A/7A0 started |
| ID-7P0 | ✅ OWNER APPROVED / CLOSED 2026-09-04 (superseded by the final-attribution and ID-7P0.2 rows below — this row is preserved for its original instrumentation-build history) — 🔄 INSTRUMENTATION LIVE — NATURAL EVIDENCE ACCUMULATION ACTIVE 2026-09-03 — narrow, owner-authorized instrumentation-only milestone (no domain design, no ADR draft, no ingestion optimization/parallelization, no cadence change, no EntryQualification/DecisionEngine change). New orthogonal, observational-only `CycleTimingRecorder`/`CallTimings` (`src/athena/observability/timing.py`) wired into `LiveIngestionEngine.run_cycle` (optional `timing=` kwarg, per-call attribution for the daily/intraday candle loops + quotes batch, additive/backward-compatible) and `DryRunCycleOrchestrator.run_cycle` (optional `enable_timing=` flag reusing the orchestrator's own existing real monotonic clock, wraps ingestion/scan into `ingestion_total`/`scan_total` phases (plus a residual, corrected by ID-7P0.1 to `orchestration_overhead_pre_final_persist`) in `runs.detail_json["timing"]`, additive, no schema change) — enabled only on the real scheduled path (`ops/scheduled_run.py`). `WorkflowEngine`'s own deterministic `_MonoClock` (business-replay determinism) is completely untouched — `owner_validation.py` was not opened. Sequentiality audit confirmed daily/intraday candle fetch are genuinely single-instrument sequential on the real Kite provider (no unused batching); quotes is genuine provider-native batch. **Provider rate-limit discovery** (corrected by ID-7P0.1, same day — see next row): a real, always-enforced pacing floor (`historical` class, 0.334s min interval ≈3 req/s, `config/providers/kite.json`) applied to the real, verified production call count (536 instruments × 3 historical calls each — `config/ingestion.json`'s actual `timeframes:["5m","15m"]`, not an assumed single timeframe — confirmed exactly against real 2026-09-03 `db/athena.db` rows) accounts for ≈539.1s ≈ 8.98 min — **≈95.8% of the observed ~9.38-minute average** — strong prior evidence (not yet measured proof) favoring `INGESTION_DOMINANT`. Business-output equivalence tested (timing on/off produce identical results). Full repository suite 3,259 passed, 0 skipped; Ruff clean; `git diff --check` clean. **Owner-authorized production restart completed 2026-09-03** (`athena serve --with-cycles`, PID 17344 → 93626, graceful — no active cycle interrupted; post-restart safety check confirmed zero artificial runs/provider calls/Decisions/EntryQualification rows, unchanged `runs` row count and latest run, and a real cycle-worker tick firing on schedule). Instrumentation is now live; natural REGULAR-cycle evidence accumulation is active, expected to begin with the 2026-09-04 session; classification remains `INSUFFICIENT_EVIDENCE` pending that evidence and a follow-up report. Owner instructed a wait state — no further ID-7 action until explicitly resumed. Full detail: `docs/research/ID-7P0-PRODUCTION-CYCLE-LATENCY-ATTRIBUTION.md` |
| ID-7P0.1 | ✅ OWNER APPROVED / CLOSED 2026-09-03 — owner review of ID-7P0 found one narrow measurement-contract inaccuracy, corrected same day (no domain design, no ADR, no ingestion optimization, no live restart). **Boundary mislabeling**: the residual phase (originally `finalization`) is derived from `duration`, which `DryRunCycleOrchestrator.run_cycle` was already measuring *before* the final COMPLETED/FAILED `RunRecord` persist call (a pre-existing fact of the class, not new) — the original doc/comment claimed it accounted for "everything else... including `save_run` calls" (plural), which was inaccurate. Renamed to `orchestration_overhead_pre_final_persist` with its exact bounded scope documented; **not fixed by adding a second write or reordering the existing one** (tested: `save_run` still called exactly twice, RUNNING then terminal, with timing on or off). Pre-existing `duration_seconds`/`detail["duration_seconds"]` fields left completely unchanged — their only consumer is a read-only CLI diagnostic print (`cli.py:458`). **Call-count correction**: the original pacing-floor estimate assumed 528 instruments and 1 intraday timeframe without checking real configuration — corrected using the actual production `config/ingestion.json` (`timeframes:["5m","15m"]`, i.e. 3 historical calls/instrument, not 2) and a read-only query of real 2026-09-03 `db/athena.db` REFRESH-cycle rows (536 instruments, 1,608 historical calls/cycle, exactly matching `datasets_validated`/`quotes_fetched` with `datasets_skipped_empty=0` — not guessed). Revised pacing floor: ≈539.1s ≈ 8.98 min ≈ **95.8%** of the ID-6E-observed ~9.38-minute average (was an unverified ≈63%). 3 new focused tests (deterministic-clock exact arithmetic proof, no-extra-repository-save proof, final-persist-boundary-exclusion proof); full repository suite 3,259 passed (was 3,256), 0 skipped; Ruff clean; `git diff --check` clean. Owner approved and closed this correction, then authorized the `athena serve --with-cycles` production restart, which has since been completed and safety-verified (see ID-7P0 row above). Full detail: `docs/research/ID-7P0-PRODUCTION-CYCLE-LATENCY-ATTRIBUTION.md` §14 |
| ID-7P0 (final attribution) | ✅ OWNER APPROVED / CLOSED 2026-09-04 — read-only final production latency-attribution audit, after the regular NSE session closed, n=21 genuine `REFRESH`/`COMPLETED` cycles from 2026-09-04. Classification `INGESTION_DOMINANT`/`HISTORICAL_CANDLE_PACING`: the deterministic `(N-1)×0.334s` pacing floor for 1,608 sequential historical calls/cycle (536 instruments × 3 calls) explains ≈95.7% of the median 560.60s cycle (ratio 1.019); analytical scan ≈1.6-2.0%; pre-final orchestration ≈0%. Recommendation classification **A — latency compensation only**, explicit caveat pending ID-7A0's own target-entry-timescale decision. Full detail: `docs/research/ID-7P0-PRODUCTION-CYCLE-LATENCY-ATTRIBUTION-REVIEW.md` |
| ID-7P0.2 | ✅ OWNER APPROVED / CLOSED 2026-09-04 — read-only run-anomaly triage, required before final ID-7P0 closure. Investigated 3 FAILED REFRESH runs (independent, ordinary transient network/transport errors during `ingestion.daily_candles`, zero business-output impact) and 1 orphaned RUNNING run (root-caused via the live production log to an owner-triggered `os.execv` service restart recovering from a stuck cycle — proven via a `409 Conflict`→`POST /api/v1/ops/restart`→same-PID-restart sequence, plus independent DB proof that the very next REFRESH run came from the owner-triggered, interval-ungated "Validate All" full-validation path (`config_snapshot_id='cfg-full-validation'`), not a scheduling-gate defect). Zero current lock/Decision/EQ/dashboard impact. Corrected §17/§25's "zero retries" overclaim (`CallTimings` never persisted a retry count) to "zero measured failed provider-call samples; retries not directly measurable" without weakening the pacing conclusion. Recommendation A re-recorded as non-binding. **ID-7A0 gate classification: `NO_ID7A0_BLOCKER`.** Full detail: `docs/research/ID-7P0-PRODUCTION-CYCLE-LATENCY-ATTRIBUTION-REVIEW.md` §38 |
| ID-7A0 | ✅ OWNER APPROVED / CLOSED — 2026-09-04; ID-7A0.1 OWNER APPROVED / CLOSED — 2026-09-04; ADR-015 ACCEPTED — 2026-09-04; ID-7A NOT STARTED (2026-09-04) — architecture/ADR-only milestone (no domain model, schema, workflow stage, API, UI, or methodology numeric formula). New artifact **`EntryActionability`** proposed: one layer downstream of `EntryQualification` (ADR-013's layer 3, WHEN/entry/risk vs. EQ's layer-2 WHETHER). Identity = the entire upstream EQ composite key copied verbatim (`instrument_id, session_date, entry_qualification_as_of, decision_id, entry_qualification_methodology_version`) plus its own `entry_actionability_as_of`/`entry_actionability_methodology_version` — no surrogate id (EQ itself has none); `decision_id` carried explicitly, mirroring EQ's own denormalization precedent. **ID-7A0.1 correction (2026-09-04, same day):** WATCH+TRADE was never actually a forced consequence of EQ-identity binding — binding only establishes the artifact cannot exist without a bound EQ row, and EQ's own scope is merely the available upstream domain. Tested against ADR-013's WHAT/WHETHER/WHEN taxonomy: `Decision=WATCH, EQ=QUALIFIED` is reachable and coherent, but surfacing WHEN/entry/risk evidence for a structurally un-authorized WATCH opportunity would misrepresent ATHENA's advisory boundary — **corrected to TRADE-only evaluation scope**, identity still generalizes, a WATCH-bound EQ still produces a `NOT_ACTIONABLE` row with an explicit "not TRADE-type" reason, never silently omitted. **ID-7A0.1 also corrected the state model**, removing a proposed 4th state (`EXPIRED`) that conflated a persisted methodology verdict with a read-time currentness judgment — an immutable, append-only row cannot express "was ACTIONABLE, no longer current" without mutation. Persisted methodology state is now 3 values (`UNKNOWN, NOT_ACTIONABLE, ACTIONABLE`); currentness/staleness is a separate, never-persisted, read-time `is_currently_usable(...)` predicate (methodology state ACTIONABLE AND bound decision_id still the current latest Decision AND evidence age within an ID-7B-decided threshold AND session constraints); evidence finality/provisionality (from bound EQ) is a third, independent dimension. Confirmed by contrast that EQ's own `EntryQualificationState.EXPIRED` remains coherent (written fresh every cycle from that cycle's own session context, never a comparison to an older row — `entry_qualification_engine.py:283-285`); upstream EQ UNKNOWN/NOT_YET/EXPIRED still produces a `NOT_ACTIONABLE` row with a preserved reason code (never silence). Historical truth stays immutable under replay (a 10:00 ACTIONABLE row still reads ACTIONABLE at 15:00, independent of `is_currently_usable` at 15:00). Directionality preserved (proven bidirectional from `TradePlan`'s own LONG/SHORT sign-flip, not assumed long-only). Four frozen timestamps (`entry_actionability_as_of`/`evidence_as_of`/`evaluated_at`/`persisted_at`) mirroring ID-6D's `persistence_clock` precedent. **Evaluation mode: Option 1 (canonical-cycle synchronous) selected, unchanged by ID-7A0.1** — new `entry_actionability` `WorkflowStage`, zero new infrastructure/provider calls, strongest possible Decision/EQ identity determinism; Options 2 (async-after-ingestion, no freshness gain given the exact-identity-binding requirement)/3 (event-driven, no event bus exists)/4 (on-demand, breaks reproducibility)/5 (hybrid, unneeded complexity) evaluated and not chosen now — full matrix in the research report. **Recommendation-A reassessment: `A_CANNOT_BE_DECIDED_UNTIL_ID7B`** (methodology question, not architecture). Zero entry/stop/target numeric methodology invented (shape only, nested immutable value objects mirroring `TradePlan`'s own pattern); zero support/resistance engine invented (none exists outside isolated DarvaX, confirmed via repo-wide search — recorded as an ID-7B/ID-8 dependency). ID-9 (sizing)/ID-10 (live supervision)/ID-11 (execution quality) boundaries explicitly preserved, no absorption. Persistence/query direction mirrors EQ's own append-only, query-convention-"latest" philosophy, extended by ID-7A0.1's `is_currently_usable(...)` predicate for "latest currently usable" (never a bare `state`-filter). Replay limitation (market-time point-in-time only, no bitemporal/knowledge-time) carried forward unresolved, exactly as ADR-013 already documents for EQ. New ADR: `docs/adr/ADR-015-intraday-actionability-architecture.md` (**Status: Accepted — 2026-09-04**). Research report: `docs/research/ID-7A0-INTRADAY-ACTIONABILITY-ARCHITECTURE.md`. Zero production code/schema/workflow-stage/API/UI/provider-call change. **ID-7A/ID-7C/ID-7D/ID-7E/ID-7F all NOT STARTED, NOT AUTHORIZED** — each needs its own separate owner authorization, mirroring ADR-013's own ID-6A0→ID-6E gated sequence |
| ID-7B | 🔄 METHODOLOGY PARTIALLY FROZEN — EVIDENCE REQUIRED FOR NUMERIC THRESHOLDS; NOT YET OWNER-APPROVED (2026-09-04) — entry/risk methodology discovery for `EntryActionability`. **Decisive finding: zero real `(TRADE, QUALIFIED)` episodes exist in production** (`db/athena.db`, read-only) — all 96,985 TRADE decisions predate EQ persistence (began 2026-09-03); all 11,986 EQ rows are WATCH-bound only. **New empirical freshness analysis** (138,454 real REGULAR-session M5 candle-pair samples, 60 instruments): median 10-min price move 0.093% (≈3.9% of typical daily range), p90 0.351% (≈13.7%), p95 0.503% (≈19.3%); VWAP-side persists unchanged 88.32% of the time over the same gap. **Canonical-cycle freshness classification: `CONDITIONAL_ON_EVIDENCE_AGE`** — typical case fine, real tail requires the extension/chase gate and `is_currently_usable`'s evidence-age term to be genuine, load-bearing gates; on that condition Option 1 remains sufficient, **no ADR-015 revision required**. **Recommendation-A reassessment: `A_CONDITIONALLY_ACCEPTED`** (compensation must be active, not passive). Frozen structurally: entry = trigger + allowable zone (VWAP-anchored primary); 5-tier invalidation hierarchy (VWAP-loss → recent completed M5 extremum → OR-level-only [never breakout-event semantics, per PS-P9B's own caution] → D1 ATR fallback → UNKNOWN); reward = `GOAL_BANDS_ONLY` (`V0_DOES_NOT_REQUIRE_GENERIC_SR`); RR informational only, not gating; `is_currently_usable` ingredients frozen (exact-EQ-currentness via full composite-key equality, not latest-Decision-id alone; provisional evidence explicitly CAN be usable). Deferred, not invented: extension cutoff, zone width, lookback window, minimum RR. **Genuine upstream (ID-6-owned) gap surfaced:** EQ's frozen v0 formula is long-biased (requires VWAP ABOVE + trend BULLISH unconditionally, no symmetric SHORT path) — EntryActionability will rarely reach a genuine SHORT opportunity today; not ID-7B's to fix. No score/ML/fitting; zero provider calls; EMR/DarvaX untouched. **ID-7B partial result Owner-reviewed and accepted as-is 2026-09-04** (status remains `METHODOLOGY_PARTIALLY_FROZEN_EVIDENCE_REQUIRED`, ADR-015 remains Accepted, no revision), ID-7B.1 authorized same day. Full detail: `docs/research/ID-7B-ENTRY-RISK-METHODOLOGY.md`. **ID-7B OWNER APPROVED / CLOSED 2026-09-04** once ID-7B.1/ID-7B.2/ID-7B.2.1 supplied the numeric-threshold evidence this row deferred — V0 methodology fully frozen |
| ID-7B.1 | 🔄 RETROSPECTIVE RECONSTRUCTION COMPLETE — TARGET COHORT SUFFICIENT; READY FOR OWNER REVIEW (2026-09-04) — research-only: reused the unmodified ID-6E replay harness pattern to run the real `EntryQualificationEngine` at each real historical TRADE decision's own checkpoint (`mode=ro`, zero writes, zero `src/` change). 96,985 TRADE decisions → 6,624 zero-invented-parameter episodes (consecutive same-instrument/session TRADE runs) → 6,624/6,624 reconstructed (100%, zero failures) → **783 TRADE+`REPLAYED_QUALIFIED` target-cohort episodes**. Sharper SHORT finding than ID-7B: zero SHORT decisions exist anywhere in the DB, any type — no SHORT population exists to test, root cause pushed upstream of ID-6, out of scope. Target-cohort evidence availability 91-100% across all evidence classes (real, not proxy). Freshness reassessed on the real cohort — VWAP-side persistence 87.11% at +10m closely matches ID-7B's own 88.32% general-population estimate (cross-validated); trend persists notably less (72.98%) — refines `CONDITIONAL_ON_EVIDENCE_AGE`, doesn't overturn it. Entry-anchor (VWAP/OR15/M5-close), invalidation-candidate (VWAP-loss/OR15-boundary/D1-ATR), and reward/risk distributions computed descriptively (no thresholds chosen); discovered same-reference-level anchor+invalidation pairs are structurally degenerate (zero risk distance) — a real constraint for future engine design. T1(+1%) hit rate 23.88%, T2(+1.5%) hit rate 14.81% (same-session horizon, frozen before calculation, no ML). RS/RVOL show a real descriptive gradient in outcome quality; Gap does not. **Reconstruction: `TARGET_COHORT_RECONSTRUCTED_SUFFICIENT`. Methodology status: `READY_FOR_ID7B2_CALIBRATION`** (only 20 distinct session dates constrain any future chronological split — flagged, not a blocker). Zero EMR/DarvaX reference. Full detail: `docs/research/ID-7B1-RETROSPECTIVE-TRADE-EQ-RECONSTRUCTION.md`. **Owner-reviewed and accepted 2026-09-04** (both classifications accepted, ADR-015 remains Accepted), ID-7B.2 authorized same day. **ID-7B.1 OWNER APPROVED / CLOSED 2026-09-04** |
| ID-7B.2 | ✅ ID-7B.2 OWNER APPROVED / CLOSED — 2026-09-04 (via ID-7B.2.1's contract correction). V0 METHODOLOGY CALIBRATED AND VALIDATED (2026-09-04) — chronological session-grouped validation (20 sessions: first 14 DISCOVERY, last 6 VALIDATION, frozen before any outcome inspected). Rebuilt the full 6,624-episode cohort (all 4 states, not just QUALIFIED) fresh. **New comparison-population evidence**: `TRADE+REPLAYED_QUALIFIED` materially outperforms `ALL_NON_QUALIFIED` on both folds (T1 26.02%/20.34% vs 8.37%/4.83% discovery/validation — separation strengthens out of sample). **Extension/chase gate: `EXTENSION_GATE_NOT_SUPPORTED`** — evidence shows the OPPOSITE of ID-7B's assumed direction (more extension = better outcomes); no gate adopted, correcting ID-7B §9. **Invalidation validated**: VWAP-loss primary (66.6%/60.0% stop-hit, stable), OR15-boundary validated secondary when COMPLETE (18.07%/15.46% stop-hit — corrects ID-7B.1's own degenerate-pairing-inflated 63.76% figure), D1-ATR → `NO_VALIDATED_FALLBACK`. **Freshness: +10m (2 completed M5 intervals) frozen** — matches ID-7P0's measured cycle duration, persistence stable cross-fold; +15m rejected (trend persistence collapses to 58.5% on validation). RR → `RR_INFORMATIONAL_ONLY`; RS/RVOL/Gap → all `CONTEXT_ONLY` (no cross-fold-stable pattern). Robustness reported (2/6 validation sessions dominate shortfall; 5.49% top-5 instrument concentration; time-of-day decline confirmed window-confounded). **`OPTION1_ACCEPTABLE_WITH_STRICT_CURRENTNESS`; Recommendation-A: `A_ACCEPTED_ONLY_WITH_CURRENTNESS_GUARD`; SHORT: `LONG_VALIDATED_SHORT_UNVALIDATED`.** **Calibration classification: `V0_METHODOLOGY_CALIBRATED_AND_VALIDATED`.** Zero ML, zero p-hacking (predeclared discovery-only thresholds, single validation pass), zero EMR/DarvaX. **Owner/Chief Architect accepted this evidence but held the final contract freeze for three consistency corrections** (2026-09-04, same day) — see ID-7B.2.1 below. Full detail: `docs/research/ID-7B2-ENTRY-RISK-CALIBRATION-VALIDATION.md` (also appended as ID-7B §37). Not marked Owner-approved/closed |
| ID-7B.2.1 | ✅ CONTRACT CORRECTED — READY FOR OWNER / CHIEF ARCHITECT FREEZE REVIEW (2026-09-04) — documentation-consistency correction only, zero recalibration/new-fold/new-threshold-search, zero calibration evidence reopened. §14's original contract recreated the exact forbidden `VWAP-anchor + VWAP-loss` degeneracy §8 itself names — corrected: entry trigger = completed M5-close checkpoint price (never VWAP); VWAP relabeled entry-location *context* only. D1 ATR removed from mandatory evidence (nothing in final V0 consumes it); OR15-boundary reframed as an always-computed contextual secondary, never a fallback substituted for VWAP-loss (no such substitution was validated) — VWAP-loss alone now explicitly drives risk-distance/RR. Freshness predicate corrected to `now − evidence_as_of <= 10 minutes` (was wrongly written against `entry_actionability_as_of`, collapsing ADR-015/ID-7A0.1's own frozen timestamp distinction; the two coincide today only as a consequence of Option 1's synchronous mode, not by definition). Also: removed a redundant `SESSION_NOT_ACTIONABLE` persisted reason (already covered by `UPSTREAM_EQ_NOT_QUALIFIED`); split persisted-state mapping from read-time currentness into two explicit blocks with a worked example proving a persisted `ACTIONABLE` row is never rewritten by a later staleness/session-closed read; resolved a methodology-version self-contradiction (content frozen, version *string* deferred to ID-7A); removed an unsupported presumption about two weak validation sessions' non-QUALIFIED population. All prior classifications (chronological split, outperformance finding, `EXTENSION_GATE_NOT_SUPPORTED`, invalidation validation, `NO_VALIDATED_FALLBACK`, `RR_INFORMATIONAL_ONLY`, `RS`/`RVOL`/`GAP_CONTEXT_ONLY`, +10m band, `OPTION1_ACCEPTABLE_WITH_STRICT_CURRENTNESS`, `A_ACCEPTED_ONLY_WITH_CURRENTNESS_GUARD`, `LONG_VALIDATED_SHORT_UNVALIDATED`, `V0_DOES_NOT_REQUIRE_GENERIC_SR`) explicitly preserved unchanged. Full detail: `docs/research/ID-7B2-ENTRY-RISK-CALIBRATION-VALIDATION.md` §29. Zero source/config/schema/test changes. **ID-7B.2.1 OWNER APPROVED / CLOSED 2026-09-04 — V0 methodology now fully frozen (ID-7B/ID-7B.1/ID-7B.2/ID-7B.2.1 all closed same day); ID-7A domain-model + persistence implementation authorized same day** |
| ID-7A | ✅ ID-7A IMPLEMENTATION COMPLETE — READY FOR OWNER / CHIEF ARCHITECT REVIEW (2026-09-05). Domain model (`src/athena/intraday/entry_actionability_models.py`): `EntryActionabilityState` (`UNKNOWN`/`NOT_ACTIONABLE`/`ACTIONABLE` only), `EntryActionabilityReasonCode` (`UPSTREAM_DECISION_NOT_TRADE`/`UPSTREAM_EQ_NOT_QUALIFIED`/`INSUFFICIENT_EVIDENCE`/`INVALIDATION_UNAVAILABLE` only), identity = full upstream EQ composite key copied verbatim + own `entry_actionability_as_of`/`entry_actionability_methodology_version` (no surrogate id), `DEFAULT_METHODOLOGY_VERSION="entry-actionability-v0"` minted, `EntryReference`/`EntryLocationContext`/`OperativeInvalidation`/`OpeningRangeContextReference`/`RewardReference` value objects exactly per the frozen V0 contract (M5-close entry, VWAP-loss invalidation paired non-degenerately, always-optional OR15-boundary context, T1/T2 goal-band reward with informational RR, no D1-ATR, no extension gate), frozen constants `T1_GOAL_BAND_PCT`/`T2_GOAL_BAND_PCT`/`CURRENTNESS_MAX_EVIDENCE_AGE_SECONDS=600.0`, direction-aware structural risk-geometry guard (rejects zero/wrong-side risk, not a calibrated minimum), bidirectional `Direction` reused unchanged, `EntryEvidenceFinality` reused directly from EQ. Read-time currentness (`entry_actionability_currentness.py`, separate module — never table columns): pure `is_currently_usable(...)` with injected `now`, exact composite-EQ-identity comparison, strict `now − evidence_as_of > 600s` STALE predicate, REGULAR-session requirement. Schema (`SCHEMA_VERSION` 17→18): new `entry_actionabilities` table (23 columns, full 7-column composite PK, single-column FK on `decision_id`, value objects as nested-JSON columns mirroring `trade_plan_json`, two supporting indexes). Repository: `save_entry_actionability` (append-only, idempotent, two independent binding validations — canonical Decision + exact upstream EntryQualification), `get_entry_actionability`, `latest_entry_actionability_for_entry_qualification` (exact-EQ-identity, never decision_id alone), `latest_entry_actionability_for_instrument_session`, `list_entry_actionabilities_for_instrument_session`. 75 new tests across 3 new files; full suite 3455 passed / 1 pre-existing unrelated skip / 0 failures. Explicitly absent (source-scan verified): `EntryActionabilityEngine` (ID-7C), workflow/API/UI wiring (ID-7E), replay/shadow (ID-7F), production actionability rows, provider calls, D1-ATR, extension-gate. `git diff --cached --stat` confirms zero touches to `WorkflowStage`, `Decision`/ID-6, ingestion, EMR, or DarvaX. **Owner/Chief Architect source review (2026-09-05): core implementation, domain/schema-v18/repository direction, and ADR-015 compliance ACCEPTED; final closure HELD for domain-integrity corrections — ID-7A.1 authorized and completed same day, see row below** |
| ID-7A.1 | ✅ ID-7A.1 COMPLETE — ID-7A READY FOR OWNER / CHIEF ARCHITECT CLOSURE REVIEW (2026-09-05). Small corrective slice: `EntryActionability.__post_init__` now rejects an ACTIONABLE verdict whose `decision_type`/`entry_qualification_state` are not truthfully TRADE/QUALIFIED, an ACTIONABLE verdict with any non-empty `reason_codes`, a `NOT_ACTIONABLE`/`UNKNOWN` reason drawn from the wrong semantic family (new `UPSTREAM_ELIGIBILITY_REASON_CODES` vs. `EVIDENCE_SUFFICIENCY_REASON_CODES` frozensets — no new codes, no evaluator-precedence rule invented), an untruthful upstream reason (e.g. `UPSTREAM_DECISION_NOT_TRADE` while `decision_type == TRADE`), and a PIT causal-ordering violation (`entry_actionability_as_of < entry_qualification_as_of` or `evidence_as_of > entry_actionability_as_of` — equality and later re-evaluation both remain valid). `is_currently_usable` now rejects `now < evidence_as_of` as an invalid temporal invocation (`ValueError`) instead of silently returning CURRENT via a negative age — no new currentness label. `EntryQualificationIdentity` gained structural validation (non-empty fields, tz-aware `as_of`). `RewardReference` rejects negative RR. `save_entry_actionability` rejects a naive `persisted_at` before any binding/insert. Preserved unchanged: `SCHEMA_VERSION` 18 (no migration), all 5 repository method signatures, append-only/idempotent semantics, the 600.0s currentness boundary, T1/T2/RR calibration, bidirectional `Direction`, and the domain-truthfulness-vs-evaluator-gate-ordering boundary. 29 new tests (illegal-ACTIONABLE-upstream rejection, reason-family consistency, truthful/untruthful upstream reasons, temporal-ordering boundaries, currentness future-evidence rejection with the 600s boundary reconfirmed, identity validation, `persisted_at` regression, and an explicit proof a real WATCH Decision + real matching QUALIFIED EQ still cannot be wrapped in an illegal ACTIONABLE — domain construction fails before persistence is ever attempted). Full suite: 3484 passed / 1 pre-existing unrelated skip / 0 failures. Zero evaluator/workflow/provider/production-row/ID-7B-methodology changes. Diff scoped to `entry_actionability_models.py`, `entry_actionability_currentness.py`, `repository.py` (+5 lines), `intraday/__init__.py` (2 new exports), and the 3 existing test files — zero schema.py/`WorkflowStage`/`Decision`/EMR/DarvaX touches. **Owner/Chief Architect source review (2026-09-05): ID-7A.1 corrections ACCEPTED; core architecture and schema-v18 ACCEPTED, must remain unchanged; final closure HELD for two narrow gaps — ID-7A.2 authorized and completed same day, see row below** |
| ID-7A.2 | ✅ ID-7A.2 COMPLETE — ID-7A READY FOR FINAL OWNER / CHIEF ARCHITECT CLOSURE (2026-09-05). Two gaps closed. **Gap 1:** `UNKNOWN` restricted reason codes to the evidence-sufficiency family but never itself required upstream eligibility (the frozen V0 structure is UPSTREAM ELIGIBILITY then LAYER-3 EVIDENCE SUFFICIENCY) — `decision_type=WATCH`+`UNKNOWN`+`INSUFFICIENT_EVIDENCE` was constructible. `UNKNOWN` now additionally requires `decision_type == TRADE` AND `entry_qualification_state == QUALIFIED` (checked before the reason-family check); an ineligible artifact's only legal state is `NOT_ACTIONABLE` (unchanged). No new reason codes. **Gap 2:** `is_currently_usable` inferred current-Decision agreement merely from EQ-identity agreement — during a real Decision→EQ pipeline-lag transient, a newer Decision `D2` can be persisted while "latest EQ" still resolves to `EQ1`/`D1`, so EQ-agreement alone would incorrectly read CURRENT. Added a mandatory `current_decision_id: str` parameter (empty rejected), compared independently of and before the EQ-identity check, in a deterministic order (input validation → temporal-impossibility → `METHODOLOGY_NOT_ACTIONABLE` → Decision mismatch → EQ mismatch → `STALE` → `SESSION_CLOSED` → `CURRENT`); either mismatch yields the same `SUPERSEDED` classification (no new persisted state/reason), explanation names which. +10m freshness/REGULAR-session checks untouched; no Decision-freshness concept added. **Call-site audit**: `is_currently_usable(` greped repo-wide — only 19 call sites, all in this milestone's own test file (no production caller yet); all 19 updated. Preserved unchanged: all ID-7A.1 corrections, `SCHEMA_VERSION` 18 (zero schema.py/repository.py diff — current-Decision resolution deliberately deferred to ID-7E, not composed here for convenience), all 5 repository method signatures. 19 new tests (13 UNKNOWN-eligibility, 6 Decision-independence/supersession). Full suite: 3503 passed / 1 pre-existing unrelated skip / 0 failures. Diff scoped to `entry_actionability_models.py` (+30 lines) and `entry_actionability_currentness.py` (+78/-15 lines) plus their 2 test files — zero schema/repository/`__init__.py`/`WorkflowStage`/`Decision`/EMR/DarvaX touches. **Owner/Chief Architect decision (2026-09-05): ID-7A.2 OWNER APPROVED/CLOSED, ID-7A.1 OWNER APPROVED/CLOSED, ID-7A OVERALL OWNER APPROVED/CLOSED (domain + persistence contract frozen, schema v18 accepted, ADR-015 remains Accepted, ID-7B V0 methodology remains frozen). ID-7C authorized same day; ID-7D/ID-7E/ID-7F remain NOT AUTHORIZED** |
| ID-7C | ✅ ID-7C IMPLEMENTATION COMPLETE — READY FOR OWNER / CHIEF ARCHITECT REVIEW (2026-09-05). New `entry_actionability_engine.py`, mirroring `EntryQualificationEngine`'s pure/deterministic contract exactly. `EntryActionabilityEngine.evaluate(*, decision, entry_qualification, market_evidence, evaluated_at, policy=None)` — no repository/provider/clock reads. Exact Decision/EQ binding validated first (decision_id/decision_type/run_id/cycle_id/instrument_id, mismatch → `ValueError`, contract error). `entry_actionability_as_of = entry_qualification.as_of` always (Option 1; V0 does not exercise future re-evaluation). Upstream gates checked together before any evidence read: `decision_type != TRADE` → `UPSTREAM_DECISION_NOT_TRADE`, exact-EQ `state != QUALIFIED` → `UPSTREAM_EQ_NOT_QUALIFIED`; both failing reports both codes (deterministic). Layer-3 only reached after TRADE+QUALIFIED: new narrow `EntryActionabilityMarketEvidence` (`completed_m5_close: Candle|None`, `session_vwap: Decimal|None`, `opening_range_15: OpeningRangeEvidence|None` — carries the raw VWAP price directly since `VwapEvidence` doesn't); missing either → `UNKNOWN`/`INSUFFICIENT_EVIDENCE`. Entry = candle's own `close`; `evidence_as_of` = candle's own completion instant (`ts_open+5min`); a not-yet-completed candle → `ValueError` (contract error). VWAP deviation = signed `(entry−vwap)/vwap×100`, unrounded, matching `indicators.calculations.vwap`'s own formula. Risk geometry (LONG: VWAP<entry; SHORT: VWAP>entry) pre-checked before domain construction — failure maps to `UNKNOWN`/`INVALIDATION_UNAVAILABLE` (never an escaping domain `ValueError`). T1/T2 = `entry×(1±T1/T2_GOAL_BAND_PCT)`, exact Decimal; RR informational-only. OR15 context (range-low for LONG / range-high for SHORT) only when `COMPLETE`, always optional, never gating/fallback/RR-affecting. `evidence_finality` echoed exactly in every branch, proven non-gating (provisional EQ still reaches ACTIONABLE). SHORT structurally supported, explicitly never claimed calibrated. 58 new tests (`tests/market_intel/test_entry_actionability_engine.py`) covering the full upstream-gate/evidence-failure/OR15/reward matrices, determinism, exact identity propagation, all binding-mismatch contract errors, and source-scan absence proofs (currentness/session-gate/persistence/latest-lookup/provider). Full suite: 3561 passed / 1 pre-existing unrelated skip / 0 failures. `SCHEMA_VERSION` unchanged at 18, zero `schema.py`/`repository.py` diff. Diff scoped to the new engine module + its test file + 8 lines in `intraday/__init__.py` — zero `WorkflowStage`/API/dashboard/ingestion/`Decision`/ID-6/EMR/DarvaX touches; zero production rows; zero provider calls. **Owner/Chief Architect source review (2026-09-05): core evaluator and V0 methodology behavior ACCEPTED; final closure HELD for three narrow provenance/coherence gaps — ID-7C.1 authorized and completed same day, see row below** |
| ID-7C.1 | ✅ ID-7C.1 COMPLETE — ID-7C READY FOR FINAL OWNER / CHIEF ARCHITECT CLOSURE (2026-09-05). Three gaps closed. **Gap 1 (VWAP provenance):** `EntryActionabilityMarketEvidence` gained `session_vwap_as_of`, frozen pairing with `session_vwap`, tz-aware validation, and an exact-equality check (whenever an M5 candle is also supplied) against that candle's own completion instant — proving M5 entry and VWAP evidence share one coherent checkpoint; a separate evaluation-time check rejects future-relative-to-checkpoint VWAP even with no M5 supplied. Missing VWAP remains legitimate `UNKNOWN`/`INSUFFICIENT_EVIDENCE`; incoherent provenance is a contract error. **Gap 2 (OR15 binding/PIT coherence):** new `_validate_or15_coherence` requires instrument/session/at-or-before-checkpoint agreement — cross-instrument/cross-session/future OR15 now raises `ValueError` instead of being silently attached. Audited `OpeningRangeEngine`'s own `elif as_of < range_end: FORMING` logic and confirmed `COMPLETE` already guarantees `range_end <= or15.as_of`, so no duplicate `range_end` check was added (documented). OR15 non-gating/non-fallback behavior unchanged. **Gap 3 (methodology-identity spoofing):** `EntryActionabilityPolicy.methodology_version` removed entirely (Option A) — the emitted `entry_actionability_methodology_version` is now always the frozen `DEFAULT_METHODOLOGY_VERSION`, no override path exists. `config_snapshot_id` remains inert audit metadata, explicitly documented as not propagated (no such field on `EntryActionability`). 17 net new tests (VWAP pairing/tz-aware/PIT-equality/future-checkpoint matrix + composite proof, OR15 coherence matrix + invalidation/RR-unchanged proof, methodology-identity removal proofs). Full suite: 3578 passed / 1 pre-existing unrelated skip / 0 failures. `SCHEMA_VERSION` unchanged at 18, zero `schema.py`/`repository.py`/`intraday/__init__.py` diff. Diff scoped to the engine module + its test file — zero `WorkflowStage`/`Decision`/ID-6/EMR/DarvaX touches; zero production rows; zero provider calls. **Owner/Chief Architect source review (2026-09-05): ID-7C.1 implementation ACCEPTED (VWAP provenance, OR15 coherence, methodology-identity freeze all accepted); final closure HELD for one narrow evaluation-order defect — ID-7C.2 authorized and completed same day, see row below** |
| ID-7C.2 | ✅ ID-7C.2 COMPLETE — ID-7C READY FOR FINAL OWNER / CHIEF ARCHITECT CLOSURE (2026-09-05). **Defect:** `evaluate()` validated candidate/checkpoint-relative layer-3 evidence (candle coherence, VWAP-vs-checkpoint, OR15 coherence) BEFORE computing upstream Decision/EQ gate reasons — so a `WATCH` Decision or non-`QUALIFIED` EQ with e.g. a cross-instrument OR15 or a future M5 candle could raise `ValueError` instead of the correct `NOT_ACTIONABLE`. **Fix:** exact Decision/EQ binding validation still runs unconditionally first (a mismatched pair is never trustworthy, eligible or not); upstream gates are now computed and the `NOT_ACTIONABLE` early return fires immediately after that, before any candidate/checkpoint-relative evidence check. Only TRADE+QUALIFIED reaches candidate/checkpoint-relative validation, then layer-3 sufficiency/geometry — eligible-path strictness fully unchanged (proven by mirrored tests). `EntryActionabilityMarketEvidence`'s own self-contained object invariants (M5 timeframe, positive VWAP, VWAP pairing, tz-aware as_of, M5/VWAP equality, OR15 window) are untouched — this is an evaluator-order correction only. 10 new tests: binding-mismatch-still-raises-first; WATCH+wrong-instrument-M5, non-QUALIFIED-EQ+future-M5, WATCH+future-checkpoint-VWAP, non-QUALIFIED-EQ+future-OR15, WATCH+cross-instrument-OR15 all now resolve to NOT_ACTIONABLE with zero ValueError; mirrored TRADE+QUALIFIED eligible-path proofs confirm strictness preserved. Full suite: 3588 passed / 1 pre-existing unrelated skip / 0 failures. `SCHEMA_VERSION` unchanged at 18, zero `schema.py`/`repository.py`/`intraday/__init__.py` diff; `evaluate()`'s public signature and the evidence-model field lists unchanged (reordering only). Diff scoped to the engine module + its test file — zero `WorkflowStage`/`Decision`/ID-6/EMR/DarvaX touches; zero production rows; zero provider calls. **Owner/Chief Architect decision (2026-09-05): ID-7C.2 OWNER APPROVED / CLOSED, ID-7C.1 OWNER APPROVED / CLOSED, ID-7C OVERALL OWNER APPROVED / CLOSED — V0 deterministic evaluator frozen.** ID-7D discovery authorized same day, see row below |
| ID-7D | ✅ ID-7D DISCOVERY COMPLETE — READY FOR OWNER / CHIEF ARCHITECT SCOPE DECISION (2026-09-05). Read-only architecture/documentation discovery resolving the "ID-7D" naming ambiguity (an older description called it "persistence," obsolete since ID-7A absorbed that scope). Reconciled ID-7 milestone history: the original pre-ID-7A0 plan (`docs/research/ID-7-INTRADAY-ENTRY-TRADEPLAN-DISCOVERY.md` §35) separated domain (original ID-7A) from persistence (original ID-7D), but the actual ID-7A authorization bundled both, fully absorbing ID-7D's scope; stale "ID-7D (persistence)" phrasing found at `ADR-015:461` and `ID-7A0-INTRADAY-ACTIONABILITY-ARCHITECTURE.md:22` (flagged, not edited — auditability preserved). Traced every `EntryActionabilityEngine.evaluate()` input to its real producer via `runtime/workflow.py` + `OwnerValidationPipeline._scan_eligible`: same-cycle Decision/EQ and OR15 already exactly coherent with zero adaptation; raw VWAP price already in context but its exact provenance (`session_vwap_as_of`) and the completed M5 candle are not yet published to `WorkflowContext` — a small single-call-site composition gap, not a methodology gap. Existing ID-7A repository contract verified sufficient (`PERSISTENCE_CONTRACT_ALREADY_SUFFICIENT`, mirroring EQ's single-write-call precedent — no new method needed). Currentness composition confirmed structurally unable to live in the write path (no "latest" query, no real wall clock, no SessionPhase resolution today) — remains a future read-time consumer's responsibility, per ADR-015. Failure semantics already covered by `WorkflowEngine`/`DailyMarketScanner` isolation. **Classification: Outcome A — ID-7D IS UNNECESSARY / HISTORICALLY SUPERSEDED** (ID-7D's original scope was absorbed into ID-7A; the EQ/ID-6D precedent shows composition logic is conventionally inlined into the one new workflow stage, not spun into its own milestone; the one real gap found is exactly analogous in size to `entry_qualification_stage`'s own inline `resolve_evidence_finality` call). Outcome B rejected on those concrete grounds; Outcome C not selected (no evidence for any other missing layer). Recommends retiring ID-7D and proceeding, once separately authorized, to ID-7E (whose design owns the identified composition work). Full ID-7E/ID-7F precondition checklists recorded in the report. Zero code/schema/repository/workflow changes; zero production rows; zero provider calls; zero Decision/ID-6/EMR/DarvaX touches. Full report: `docs/research/ID-7D-NEXT-LAYER-DISCOVERY-CONTRACT-RECONCILIATION.md`. **Owner/Chief Architect decision (2026-09-05): ID-7D DISCOVERY OWNER APPROVED / CLOSED, Classification A accepted — ID-7D's persistence scope was absorbed into ID-7A; no separate ID-7D implementation exists.** ADR-015/ID-7A0 report stale references corrected in place same day; the report's own §20 `persisted_at` overstatement corrected (stored but not exposed by current repository reads). ID-7E authorized same day, see row below; ID-7F remains NOT STARTED, NOT AUTHORIZED |
| ID-7E | ✅ ID-7E IMPLEMENTATION COMPLETE — READY FOR OWNER / CHIEF ARCHITECT REVIEW (2026-09-05). New `entry_actionability` `WorkflowStage` in `OwnerValidationPipeline._scan_eligible`'s per-instrument DAG, `depends_on=("entry_qualification",)` only (transitive-dependency guarantee proven structurally, not by insertion order). Reads the exact same-cycle Decision and the exact EntryQualification `entry_qualification_stage` produced this cycle -- never a repository "latest" query. `ind_stage` now also publishes `latest_completed_m5` (the exact completed M5 candle VWAP was computed from, via `session.latest_completed_candle` over the same bounded series -- never a second read); `session_vwap_as_of` is derived from that candle's own completion instant, naturally satisfying the engine's exact VWAP-provenance equality check. OR15 reuses `IntradaySignalSet.or15` directly. One captured wall-clock instant reused for both `evaluated_at`/`persisted_at`; engine invoked with `policy=None`. Persistence scoped to WATCH/TRADE (mirrors EQ's own persistence gate -- required, since EntryActionability's binding validation needs the referenced EQ to itself be a persisted row), preserving ADR-015's frozen WATCH->NOT_ACTIONABLE contract. 11 new tests: DAG/order proof, transitive-dependency structural proof, exact binding-identity proof, WATCH->NOT_ACTIONABLE, a full real-pipeline run reaching genuine ACTIONABLE with exact entry/VWAP/invalidation/reward/provenance values, UNKNOWN/INSUFFICIENT_EVIDENCE, UNKNOWN/INVALIDATION_UNAVAILABLE, a genuine contract error proven isolated to one instrument (Decision/EQ persistence from earlier stages survives; a healthy sibling instrument unaffected), idempotent re-run, and zero-currentness/zero-provider/zero-policy source-scan proofs. Full suite: 3599 passed, 1 pre-existing unrelated skip, 0 failures. `SCHEMA_VERSION` unchanged at 18; zero diff to schema/repository/`intraday/__init__.py`/the engine or domain modules; zero Decision/ID-6/EMR/DarvaX touches; zero new API/UI; zero currentness in the write path; zero provider calls; no production restart/replay performed. Not marked Owner-approved. **ID-7F remains NOT STARTED, NOT AUTHORIZED** |

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

As of ID-6E.2 (2026-09-03): **3,190 passed, 1 pre-existing
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

The owner approved the ID-6D.1 persistence-time correction and closed
ID-6D (including ID-6D.1) in full on 2026-09-02, then authorized ID-6E to
validate the now fully closed Entry Qualification chain.

ID-6E's analysis is complete:
`docs/research/ID-6E-ENTRY-QUALIFICATION-REPLAY-SHADOW-VALIDATION.md`.
Validation only — no methodology, threshold, workflow, or engine change.
A new harness, `src/athena/data/id6e_replay_shadow_validation.py`, reused
ID-6B.1's `ReadOnlyStore`/`candidates_at` and ID-6B.1B's own
deterministically-selected 10-session/17,082-observation window verbatim,
but — unlike every prior ID-6B research harness — calls the real, closed
`EntryQualificationEngine.evaluate()` and `resolve_evidence_finality()`
directly rather than re-deriving the v0 formula. Two independent full
replay runs produced an exactly matching SHA-256 analysis digest (full
determinism, zero provider/network calls). Every headline statistic
matches ID-6B.1B's own research-formula figures almost exactly (QUALIFIED
21.70%, TRADE match 24.17%, WATCH match 19.93%, checkpoint-level flicker
39.76%) with zero tuning performed to force the agreement — direct
confirmation that the production engine faithfully implements the frozen
methodology. All frozen invariants held across all 17,082 observations
(`DISQUALIFIED_FOR_SESSION` count 0, confirmation always `NOT_EVALUATED`,
0 harness defects, 0 coherence failures); Option C and M15's
non-blocking-technical-debt status were both reconfirmed at full
production-engine scale. Evidence-finality was 100% `LIVE_M5_PROVISIONAL`,
exactly as ID-6D's resolver predicts for REGULAR-phase WATCH/TRADE
evaluation, with the historical-replay-vs-storage-settlement distinction
(ID-6D.1's own owner-accepted limitation) explicitly restated.

The real production `db/athena.db` was audited read-only
(`mode=ro`+`PRAGMA query_only=ON`): the `entry_qualifications` table does
not exist in production yet — the ID-6C schema migration has never been
run against it. This was reported honestly as
`SHADOW_OBSERVATIONS_NOT_YET_AVAILABLE`; no synthetic rows were fabricated
to satisfy the milestone. Classification:
**`REPLAY_SOUND_SHADOW_EVIDENCE_INSUFFICIENT`**. No profitability, edge,
win-rate, or target-hit claim was made or tested — outcome data was not
even queried. 18 new focused tests (9 pure-function, 5 harness
integration, 4 shadow-audit), 2 mutation-verified.

Owner review accepted the replay architecture, engine/state/finality
analysis, and the shadow-unavailable classification, but held closure for
one defect: `_transitions`/`_qualified_duration` grouped trajectories by
`(instrument_id, session_date, decision_type)` — a `DecisionType` is not a
Decision identity, and a newer canonical Decision superseding an older one
of the same type within one instrument/session was wrongly merged into a
single trajectory, inflating apparent flicker to 39.76%.

**ID-6E.1 corrected this.** `_transitions`/`_qualified_duration` now group
by `(instrument_id, session_date, decision_id)` — the genuine canonical
Decision episode ID-6C/ID-6D already bind Entry Qualification to — ordered
by the semantic `as_of` timestamp rather than the checkpoint label. A new
descriptive `_decision_supersession` audit found Decision churn is the
norm in this population: 3,210 of 3,401 instrument/session groups (94.4%)
contain more than one distinct Decision episode across the 6 replay
checkpoints, 14,699 total distinct episodes. Corrected flicker: 215 of
1,833 multi-checkpoint episodes = **11.73%** — materially lower than the
superseded 39.76%, root-caused to the old grouping conflating an average
of several Decision episodes per instrument/session group. ID-6B.1B's own
`_transitions` was audited and found to share the identical
`decision_type`-grouping defect, predating ID-6E entirely (a research-only
contract written before ID-6C's Decision-binding persistence discipline
existed) — per the owner's instruction, ID-6B.1B's own historical
artifacts were not modified; the semantic difference is documented in the
corrected research report instead. All point-observation invariants
(state distribution, WATCH/TRADE split, Option C, M15, finality,
confirmation, methodology version) were reconfirmed byte-for-byte
unchanged, and a new deterministic digest
(`d18c2cb1c43688804c7aea8430b1d4a1539c48f4b3cab3e2a05fd2bba8a70ef9`)
matched exactly across two independent reruns of the full 17,082-
observation replay against real `db/athena.db`. 5 new focused tests
(2 mutation-verified — reverting the grouping to `decision_type` correctly
failed the new Decision-identity tests, then was reverted), 23/23
`test_id6e_replay_shadow_validation.py` passing, combined ID-6A–ID-6E
Entry Qualification suite 194 passed. Full repository suite: 3,154
passed, 1 pre-existing skip, 0 failed. `db/athena.db` confirmed unmodified
(identical checksum) across all replay runs and the shadow audit. The
owner approved ID-6E.1 and accepted the historical replay validation as
**BEHAVIORALLY SOUND**.

**ID-6E.2 (2026-09-03) then opened and progressed shadow validation.**
Owner-authorized, operational-only: preflight against real `db/athena.db`
found SCHEMA_VERSION already 17 with `entry_qualifications` present (0
rows) — migration had already occurred via ATHENA's own routine, idempotent
`SqliteRepository.initialize()` calls at `_open_repo()`/API startup (the
already-running `athena serve --with-cycles` process had already exercised
this canonical, additive-only path); no ad-hoc migration SQL was issued.
An integrity-verified, checksummed safety backup was taken immediately
(`db/backups/athena-pre-id6e2-shadow-canary-20260903T024201Z.db`).
Structural verification against a freshly-initialized v17 reference schema
found zero drift (28/28 tables, 56/56 indexes, exact `entry_qualifications`
column/PK/FK/index match); migration idempotency was explicitly
reconfirmed via a second `initialize()` call (record counts, table set,
index set all unchanged).

The shadow canary used the normal runtime path throughout: no manual SQL,
no direct `save_entry_qualification()` call, no fabricated data. The
already-running, already-scheduled production server fired its own
PREMARKET cycle (08:15:29 IST) entirely on its own schedule; this milestone
only observed it read-only, polling until the `entry_qualification` stage
persisted **165 genuine rows** — one per eligible WATCH candidate. A
full-population (not sampled) integrity audit found zero defects across
all 165 rows (Decision-binding, timezone/session-date coherence, reason
codes, methodology version, confirmation, duplicate identity — all clean).
Every row shares `state=EXPIRED`/`evidence_finality=UNKNOWN_PROVENANCE`/
`decision_type=WATCH` — read-only root-caused (no frozen code touched) to
the cycle's 08:15 `as_of` falling before `config/market.nse.json`'s
`preopen_start` (09:00), so `classify_session_phase` correctly returns
`SessionPhase.CLOSED` for this `as_of`, which the frozen engine/resolver
correctly map to `EXPIRED`/`UNKNOWN_PROVENANCE` — verified as intentional,
by-design behavior, not a defect. Genuine persistence latency was measured
for the first time in production: median 550.77s, p90 552.58s, max
553.12s, 0 negative-latency rows.

**Classification impact.** Runtime persistence is now proven operational
against production; the single CLOSED-phase moment observed does not yet
support behavioral shadow characterization (no REGULAR-phase, QUALIFIED/
NOT_YET/UNKNOWN, or TRADE observation exists yet) — no arbitrary
sample-size threshold was invented to claim otherwise. No new production
code was added; full repository suite 3,190 passed, 1 pre-existing skip,
0 failed. Full record:
`docs/ops/ID-6E2-ENTRY-QUALIFICATION-PRODUCTION-SCHEMA-ACTIVATION.md`.

The owner approved ID-6E.2 and closed it in full on 2026-09-03: production
schema activation CLOSED, production runtime persistence canary CLOSED,
shadow accumulation ACTIVE — and authorized ID-6E.3 to inspect the
genuine observations accumulating naturally through the already-running
scheduler, to determine whether REGULAR-session behavior could now be
characterized.

**ID-6E.3 is read-only characterization only** — no production writes, no
scheduler trigger, no config change. A deterministic audit cutoff was
fixed first (`persisted_at <= max(persisted_at)` at audit start =
`2026-09-03T04:09:59.748488+00:00`, bounding the analysis to exactly 654
rows) so a continuously-accumulating live table could not make the report
internally inconsistent (production had grown to 893 rows by report time
— noted for context only, never analyzed).

The bounded population spans exactly 3 distinct `as_of` values (one per
real scheduled cycle). Each was classified using the actual, unmodified
`classify_session_phase` (`src/athena/session/engine.py`), imported
read-only: 08:15:29 IST → `SessionPhase.CLOSED` (165 rows, unchanged from
ID-6E.2); 09:15:16 and 09:30:40 IST → **`SessionPhase.REGULAR`** (489 rows
total) — the first genuine REGULAR-phase shadow evidence to exist. The
REGULAR population (489 rows, 100% WATCH, 100% `entry-qualification-v0`)
holds its required finality invariant **exactly**: 489/489
`LIVE_M5_PROVISIONAL`, 0 violations; 0 `DISQUALIFIED_FOR_SESSION`; state
distribution NOT_YET 65.44%, UNKNOWN 19.02%, QUALIFIED 15.54%.
Checkpoint-level detail cleanly explains the UNKNOWN concentration: 33.7%
UNKNOWN at 09:15:16 (essentially the literal instant of market open, when
few M5 candles have completed — 87 of 93 UNKNOWN rows cite
`VWAP_EVIDENCE_UNAVAILABLE`) dropping to 3.0% by 09:30:40 — a genuine,
sensible live-market artifact, not a defect, and one replay's own earliest
checkpoint (09:30, already 15 minutes post-open) never exercised.

A full-population integrity audit (all 654 rows, not just REGULAR) found
**zero defects of any kind**: Decision-binding mismatches, orphaned
`decision_id`, duplicate logical identity, timezone/session-date
incoherence, invalid enums, malformed JSON, `DISQUALIFIED_FOR_SESSION`,
non-`NOT_EVALUATED` confirmation, non-v0 methodology — all 0.

The canonical `(instrument_id, session_date, decision_id)` trajectory
grouping (per ID-6E.1 — never `decision_type`) found all 489 REGULAR
Decision episodes to be **single-checkpoint**: **0 multi-checkpoint
episodes exist.** 231 of 258 instrument/session groups (89.5%) already
show more than one distinct `decision_id` across just these first 2
checkpoints — essentially every instrument's Decision is re-issued each
cycle. **Consequence: genuine shadow flicker is not yet measurable** —
reported as a real evidentiary gap, never approximated or forced with an
invented minimum sample size. 0 TRADE decision-type observations exist
anywhere in the bounded population. Option C is not reconstructable from
persisted evidence (`entry_qualifications` does not store
`SessionContext.data_quality` or any `EXPECTED_BAR_MISSING`-equivalent
marker) — reported honestly rather than inferred or refetched. NOT_YET/
QUALIFIED root causes directionally match replay's own findings exactly.
Persistence latency (median ~551-556s across all three cycles, 0 negative)
confirms ID-6E.2's own observation was not PREMARKET-specific.

Checkpoint-matched replay comparison (shadow's 09:30:40 vs. replay's own
09:30 checkpoint) is far more informative than a blended aggregate:
QUALIFIED 32.5% vs. 22.95%, UNKNOWN 3.0% vs. 1.08% — closer once
population differences (near-open checkpoint timing, one real day vs. a
10-session average, live/provisional vs. settled historical data) are
documented before interpreting. Flicker cannot be compared at all: shadow
has 0 multi-checkpoint episodes against replay's 11.73% corrected figure.

**Classification: `REPLAY_SOUND_SHADOW_EVIDENCE_STILL_ACCUMULATING`.**
Every observed runtime row remains clean and genuine REGULAR evidence now
exists, directionally consistent with replay on every comparable
dimension — but Decision-episode trajectories/flicker and TRADE-type
representation both have zero data points so far, the expected shape of
one real trading morning's first two REGULAR cycles, not a defect. No
source code was changed; full repository suite 3,190 passed (unchanged),
1 pre-existing skip. Full record:
`docs/research/ID-6E-ENTRY-QUALIFICATION-REPLAY-SHADOW-VALIDATION.md`
§50.

The owner approved ID-6E.3 in full on 2026-09-03 and issued a wait-state
directive: **ID-6E overall remains OPEN**
(`REPLAY_SOUND_SHADOW_EVIDENCE_STILL_ACCUMULATING`); shadow accumulation
continues through the already-running production scheduler; **no new
implementation milestone is authorized**; the current genuine shadow
limitations (0 TRADE observations, 0 multi-checkpoint Decision episodes,
1 trading session at the ID-6E.3 cutoff) are explicitly accepted as
genuine, not a defect, and must never be "solved" by manually triggering
cycles, changing cadence/thresholds, injecting synthetic Decisions, or any
other artificial evidence-forcing. Decision churn (89.5% at the ID-6E.3
cutoff, also high in historical replay) must never become a mandatory
"multi-checkpoint same-decision_id trajectory must exist" engineering
prerequisite — the runtime may legitimately reissue a fresh canonical
Decision every cycle. The next read-only shadow review happens only once
evidence *materially* changes (a later REGULAR cycle, a second session, a
TRADE observation, a multi-checkpoint Decision episode, or enough
independent checkpoints for a meaningful behavioral comparison) — never on
a fixed schedule, and never by repeatedly auditing after every scheduler
tick. When that next review happens, it must remain read-only
(`mode=ro`+`PRAGMA query_only=ON`, a deterministic audit cutoff, zero
provider calls, zero production mutation) and reuse the exact canonical
trajectory identity ID-6E.1 established — `(instrument_id, session_date,
decision_id)` ordered by `as_of`, never `decision_type` — the accepted
historical canonical flicker (11.73%, for the frozen 17,082-observation
replay population) remains a reference metric, never a production target,
and replay/shadow populations must always be kept distinct (population/
date/cadence/live-provisional differences documented before interpreting
any deviation).

**Carry-forward architectural note for a future ID-7 (not started, not
designed here).** Production shadow evidence has now repeatedly shown
`persisted_at - as_of` ≈ 9.2 minutes for full-universe cycles (ID-6E.2's
PREMARKET cycle and both of ID-6E.3's REFRESH cycles). This is **not** an
ID-6 correctness defect — the `EntryQualification` result stays correctly
bound to its market/evidence checkpoint `as_of`, exactly as ID-6D.1
designed. When ID-7 is eventually authorized, it must explicitly
distinguish "qualified for market state at time T" from "still
actionable/executable at wall-clock time T + processing latency." This is
recorded here only as a carry-forward requirement — it is not solved,
designed, or implemented inside ID-6.

Do not add API/UI, thresholds, IntradayTradePlan, an M15 settlement-repair
milestone, ID-7, EM-6, EMR, DarvaX, or order behavior. Do not implement
anything further for ID-6E until the owner explicitly requests the next
read-only shadow review. Do not owner-close ID-6E overall.

**Closure-gate clarification (2026-09-03, documentation only — no source/
DB/scheduler change).** A read-only architectural check, informal and
outside ID-6E.3's own bounded audit, found that production issues a
brand-new canonical Decision for every instrument on every synchronous
cycle — `decision_id` literally embeds that cycle's own timestamp (e.g.
`decision-NSE:360ONE-2026-09-03T08:15:29...`,
`...T09:15:16...`, `...T09:30:40...`, `...T09:43:53...` for the same
instrument across successive real cycles), never reusing a prior cycle's
Decision. This exactly matches ID-6D's own accepted design ("Current
Decision = the Decision produced this same synchronous cycle"). The owner
used this fact to clarify — never reopen or reinterpret — what remains
required for ID-6E's overall closure:

1. **Same-Decision multi-checkpoint episodes are architecturally not
   expected** under the current REFRESH cadence (unlike historical
   replay's 94.4%-not-100% Decision churn, explained by real gaps between
   replay checkpoints occasionally leaving no newer Decision to select,
   never by production reusing one) — **their absence is no longer a
   closure requirement**, though still reported if naturally present.
2. ID-6E.1's canonical `(instrument_id, session_date, decision_id)`
   trajectory grouping **remains correct** and must never be regressed to
   `(instrument_id, session_date, decision_type)` merely to manufacture a
   production flicker figure — that would silently reintroduce the exact
   defect ID-6E.1 corrected. The corrected historical replay flicker
   (11.73%) remains valid for the historical replay population only.
3. **TRADE observation and a second trading session both remain
   desirable but are not mandatory** for closure — market-dependent,
   never to be forced.
4. **The revised, sole remaining closure gate**: genuine REGULAR-session
   shadow observations across *several* naturally scheduled, independent
   checkpoints spanning meaningfully different portions of the live
   session (beyond the 09:15 open-edge and 09:30 early checkpoint ID-6E.3
   already characterized) — descriptive, not an invented numeric
   threshold, achievable within a single trading day (no calendar-day
   waiting requirement).

Two carry-forward concepts are recorded, explicitly **not** implemented
and **not** part of ID-6E: cross-Decision stability (how consistent Entry
Qualification is for the same instrument across *successive, distinct*
Decisions — a different metric from same-Decision flicker, needing its
own future semantic definition, never to be smuggled into ID-6E's own
closure criteria) and the already-accepted ID-7 actionability-latency
requirement (§ above — `persisted_at - as_of` ≈ 9.2 minutes, not an ID-6
defect, but ID-7 must distinguish "qualified for market state at T" from
"actionable at wall-clock T + processing latency").

**Final post-market shadow audit (owner-authorized, 2026-09-03, after the
full trading session closed).** Bounded population `persisted_at <=
2026-09-03T10:24:33.966703+00:00` — **6,640 rows** across **28 distinct
`as_of` checkpoints** (1 PREMARKET, 26 REFRESH, 1 CLOSING), the entire
completed session, vs. ID-6E.3's 654-row/3-checkpoint slice. `SessionPhase`
via the frozen `classify_session_phase`: CLOSED 420 (PREMARKET + CLOSING),
**REGULAR 6,220**. REGULAR state distribution: NOT_YET 73.82%, QUALIFIED
17.75%, UNKNOWN 8.44%. REGULAR finality invariant holds exactly
(6,220/6,220 `LIVE_M5_PROVISIONAL`); confirmation invariant holds exactly
(6,640/6,640 `NOT_EVALUATED`); methodology invariant holds exactly
(6,640/6,640 `entry-qualification-v0`). Decision-binding audit against the
real `decisions` table: **0 defects of any kind** (0 missing, 0
decision_type/run_id/cycle_id/instrument mismatches) across all 6,640
rows. 0 duplicate logical identities, 0 naive timestamps, 0 malformed
JSON. UNKNOWN, tracked checkpoint-by-checkpoint across the whole session,
is concentrated at the 09:15 open (33.73%) then settles into a
**2.99-15.08% band for the rest of the day** — never returning to the
open-edge extreme, never trending toward zero or growing pathologically —
answering ID-6E.3's own open question about later-session UNKNOWN
behavior. Decision churn: 295/301 (98.01%) instrument/session groups show
more than one distinct `decision_id` across the day, and canonical
same-Decision episodes remain **0 multi-checkpoint** even across 28
checkpoints — confirming, with much stronger evidence than ID-6E.3, the
closure-gate clarification's architectural explanation (fresh Decision
per instrument per cycle makes same-Decision multi-checkpoint episodes
structurally near-impossible, not merely rare — `PRODUCTION_SAME_DECISION_
FLICKER_NOT_MEASURABLE`, not a gap). TRADE remained absent for the entire
session (`TRADE_SHADOW_EVIDENCE_NOT_OBSERVED` — the same day's market
regime stayed SIDEWAYS/`Direction.NONE` for its entirety, structurally
blocking canonical TRADE Decisions; a market fact, not an Entry
Qualification defect). Persistence latency: median 562.97s (~9.4 min)
overall, per-checkpoint medians 543.9-619.3s, 0 negative-latency rows —
confirming the ~9-10 minute shape is stable across an entire session, not
just its opening cycles. Checkpoint-aware replay comparison found two
closely-aligned checkpoints (09:30, 10:00, both within ~1 minute) with
directionally higher shadow QUALIFIED than replay, and explicitly did
**not** force a comparison at 13:00/14:30 where the nearest shadow
checkpoint was more than 5 minutes off (reported for context only, not as
a match). Two independent full audit runs against the identical bounded
population produced a byte-identical SHA-256 digest — full determinism.
Before/after `PRAGMA integrity_check`/`foreign_key_check`/schema-version/
row-count snapshots were identical — **zero milestone mutation**. Full
detail: `docs/research/ID-6E-ENTRY-QUALIFICATION-REPLAY-SHADOW-VALIDATION.md`
§53.

**Classification: `REPLAY_AND_SHADOW_BEHAVIORALLY_SOUND`.** Owner/Chief
Architect reviewed and accepted this audit on 2026-09-03:
**ID-6E OWNER APPROVED / CLOSED**, and **ID-6 OVERALL OWNER APPROVED /
CLOSED** (the entire track — ADR-013/ID-6A0 through this final ID-6E
audit). Full detail: `docs/research/ID-6E-ENTRY-QUALIFICATION-REPLAY-SHADOW-VALIDATION.md`
§53 (see also the doc's own final Owner Decision / Closure section). The
frozen v0 methodology, state semantics, and finality semantics (§§3-5 of
the owner's closure decision) remain exactly as validated — no
weighted score, no threshold, no hysteresis/debounce/stickiness added.
`PRODUCTION_SAME_DECISION_FLICKER_NOT_MEASURABLE` and
`TRADE_SHADOW_EVIDENCE_NOT_OBSERVED` are both recorded as accepted facts
about this population, not closure defects. **ID-7 is NOT STARTED** —
this closure does not by itself authorize it; a future ID-7 discovery
must carry forward the ~9-10 minute processing-latency finding as a
mandatory design input, never solved retroactively inside ID-6.

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
