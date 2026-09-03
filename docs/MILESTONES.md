# ATHENA — Milestone Roadmap

Official milestone roadmap per the milestone-based workflow (AGENTS.md).
One milestone at a time; owner approval gates every transition. A milestone
too large for a single-sitting review is split BEFORE implementation.

## Portfolio Sync Track (PS-P0 started 2026-09-01)

**Source:** Owner assignment dated 2026-09-01 / 2026-09-02

**Reports:** `docs/research/PS-P0-PORTFOLIO-SYNC-DISCOVERY-REPORT.md`,
`docs/research/PS-P1-PORTFOLIO-CONTRACT-DESIGN.md`,
`docs/research/PS-P2-PORTFOLIO-IMPORT-RECONCILIATION.md`,
`docs/research/PS-P3-MY-PORTFOLIO-DASHBOARD-UX.md`,
`docs/research/PS-P4-PORTFOLIO-SYNC-ORCHESTRATION.md`,
`docs/research/PS-P5A-PORTFOLIO-INTERPRETATION-METHODOLOGY.md`,
`docs/research/PS-P5B-PORTFOLIO-INTERPRETATION-IMPLEMENTATION.md`,
`docs/research/PS-P6A-PORTFOLIO-EXPERIENCE-HARDENING-DISCOVERY.md`,
`docs/research/PS-P6B-PORTFOLIO-EXPERIENCE-HARDENING-IMPLEMENTATION.md`,
`docs/research/PS-P6C-MY-PORTFOLIO-V1-END-TO-END-VALIDATION.md`

Adds a My Portfolio dashboard feature/subdomain inside ATHENA's existing
portfolio capability. The feature owns imported current holdings,
reconciliation, portfolio sync, and 20-column Portfolio Snapshot contracts while
preserving ATHENA's advisory-only boundary and never modifying core
ScoringEngine/DecisionEngine methodology.

| Milestone | Objective | Status |
|---|---|---|
| PS-P0 | Discovery only — audit existing portfolio, market-data, API, dashboard, symbol, and analytics surfaces before designing My Portfolio | ✅ Owner/Chief Architect approved 2026-09-02 |
| PS-P1 | My Portfolio Design, Schema & API Contracts — freeze module boundary, source of truth, isolated persistence, import/reconciliation contracts, Sync Portfolio contract, freshness/provenance/null semantics, and the complete 20-column Portfolio Snapshot API DTO | ✅ Owner/Chief Architect approved 2026-09-02 |
| PS-P2 | Import Preview & Holdings Reconciliation — CSV/XLSX parse, normalize, validate, resolve symbols, persist preview, show deterministic reconciliation, confirm atomically, update canonical holdings, preserve audit history | ✅ Owner/Chief Architect approved 2026-09-02 |
| PS-P3 | My Portfolio Dashboard + Upload UX — separate dashboard tab over PS-P2 APIs with server-side upload preview, mapping/error review, reconciliation diff, explicit confirmation, current holdings, and import history | ✅ Owner/Chief Architect approved 2026-09-02 |
| PS-P4 | Portfolio Sync Orchestration — background sync over confirmed My Portfolio holdings, persisted sync runs, immutable 20-column analysis snapshots, server-owned valuation math, latest snapshot API, dashboard sync polling/rendering, and PS-P4.1 freshness/evidence coherency correction | ✅ Owner/Chief Architect approved 2026-09-02 — PS-P4 and PS-P4.1 frozen |
| PS-P5A | Portfolio Interpretation Methodology Discovery & Freeze — inventory actual ATHENA evidence, propose deterministic portfolio Status/Conviction/Trend/Trigger/Support/Exit/Target/Next Action methodology, reason codes, test vectors, and owner decisions before production implementation | ✅ Owner/Chief Architect approved subset for PS-P5B implementation 2026-09-03 |
| PS-P5B | Portfolio Interpretation Implementation — implement only the Owner/Chief Architect-approved PS-P5A subset in the pure interpreter, Portfolio Sync snapshot wiring, dashboard/API rendering, and regression tests | ✅ Owner/Chief Architect approved 2026-09-03 |
| PS-P6A | Portfolio Experience Completion & Operational Hardening Discovery — inspect actual My Portfolio import/confirm/holdings/sync/snapshot/dashboard workflow after PS-P5B and identify remaining production-readiness gaps before implementation | ✅ Owner/Chief Architect approved 2026-09-03 |
| PS-P6B | Portfolio Currentness, Concurrency & Operational Hardening — expose server-owned latest snapshot currentness, preserve stale snapshots visibly, block import confirmation during active sync while allowing preview, and clarify partial/failure/explanation UX | ✅ Owner/Chief Architect approved and frozen 2026-09-03 after UNKNOWN currentness UX correction |
| PS-P6C | My Portfolio V1 End-to-End Production Validation — validate the complete frozen V1 owner workflow, failure/recovery/currentness/API/dashboard/input/performance scenarios, and recommend final V1 freeze if all criteria pass | 🔄 Validation complete 2026-09-03 — ready for Owner/Chief Architect review; recommendation: My Portfolio V1 complete and frozen |

## Intraday Intelligence Track (ID-0 started 2026-08-29)

**Source:** Owner assignment dated 2026-08-29

**Report:** `docs/research/ID-0-RUNTIME-AUDIT-ARCHITECTURE-REPORT.md`

Extends ATHENA with intraday opportunity identification/management (targeting
~1-1.5% moves) while preserving the existing daily/structural pipeline.
Conceptual separation: DAILY/STRUCTURAL (what's worth watching) →
INTRADAY (whether it's actionable now) → ENTRY/EXECUTION (when/at what
price) → LIVE PLAN SUPERVISION (still valid?). Advisory-only; no
order-placement code, ever. Sequenced ID-0 → ID-13, one milestone at a time,
never auto-continuing past an owner approval gate.

| Milestone | Objective | Status |
|---|---|---|
| ID-0 | Runtime audit + architecture freeze — verify current data flow, `PipelineContext` reality, indicator reusability, Sector Health wiring, `TradePlan`/freshness machinery, and provider data availability; propose (not implement) the smallest architecture-compatible intraday extension | ✅ Approved with conditions 2026-08-29 — recommendation GO WITH CONDITIONS accepted; conditions addressed by ID-P0/ID-P0.1 below |
| ID-P0 | Prerequisite: resolve the ADR-003 dormant-vs-live ambiguity + wire existing Sector Health into live scoring/evidence/decision — the two architectural inconsistencies ID-0 found, cleared before any new intraday stage is added | ✅ Owner approved 2026-08-29 — full suite green (2,717 passed, 1 pre-existing skip) |
| ID-P0.1 | Measurement-only checkpoint: quantify the real historical decision/composite impact of activating Sector Health, via a deterministic replay against a scratch copy of the real production book — no tuning | ✅ Owner approved 2026-08-29 — measured impact accepted; no threshold recalibration performed |
| ID-1 | Intraday Data Semantics & Session Context Foundation — explicit intraday provenance, deterministic completed-candle semantics, a `SessionContext` artifact, session-data-quality UNKNOWN semantics. Foundation only: no signals, no scoring/threshold change | ✅ Owner approved 2026-08-29 — `athena.session` package + one new live `WorkflowStage`; full suite green (2,743 passed, 1 pre-existing skip) |
| ID-2 | Intraday Analytical Context & Trend Foundation — `IntradaySignalSet`/`IntradayTrendContext` typed evidence formalizing the existing live VWAP relation + 5m/15m confluence direction. Still foundation: no EntryQualification, no new gates, no scoring change | ✅ Architecture accepted 2026-08-29 (contract, single-authoritative-calculation principle, `WorkflowStage` integration, isolation) — **not fully closed**: a completed-candle correctness gap found in owner code review, fixed by ID-2.1 below |
| ID-2.1 | Corrective: `ind_stage`'s VWAP/confluence inputs did not filter through ID-1's completed-candle rule, so a still-forming 5m/15m bar could silently influence them even though `SessionContext` already knew it wasn't complete. Fix input-time correctness only — no VWAP formula, confluence period, or scoring weight/bonus changed. Also: rename the disagreement trend label `NEUTRAL` → `MIXED` (owner decision) | ✅ Owner approved 2026-08-29 — one authoritative `athena.session.completed_candles()` filter now governs both VWAP and confluence; full suite green (2,768 passed, 1 pre-existing skip) |
| ID-3 | Opening Range Intelligence — `OpeningRangeEvidence` (OR15/OR30 parallel windows, neither canonical) as new typed evidence in `IntradaySignalSet`. First genuinely new intraday methodology, still evidence-only: no Decision gate, no TradePlan change, no EntryQualification | ✅ Architecture + ORB evidence contract accepted 2026-08-29 — **not fully closed**: two production correctness issues found in owner code review (shared `limit=100` candle retrieval; ORB slot-count-vs-canonical-slot completeness), fixed by ID-3.1 below |
| ID-3.1 | Corrective: (A) session-scoped candle reads (`session_stage`, VWAP, ORB) used a fixed `list_candles_recent(limit=100)`, proven by ID-3's own real-data check to silently drop a session's own opening bars on a high-row-density day; (B) `OpeningRangeEngine` judged range completeness by raw in-window row count, so an off-grid timestamp could substitute for a genuinely missing canonical slot. Fix retrieval semantics + canonical-slot integrity only — no new signal methodology, no scoring/Decision/TradePlan change | ✅ Owner approved 2026-08-29 — bounded `get_candles()` reads (no new repository method) + `OpeningRangeEngine._canonical_slots()`; real-data acceptance check on the production retrieval path: OR15 526/526 COMPLETE, OR30 3/526 COMPLETE (523 honestly INCOMPLETE_DATA — a real, previously-masked finding, not a regression); full suite green (2,806 passed, 1 pre-existing skip) |
| ID-4 | Market → sector → stock `RelativeStrengthContext` — point-in-time comparative performance evidence, not RSI, not a scoring input, not a market→sector→stock gating chain | ✅ Architecture accepted 2026-08-29 — **not fully closed**: a common-cutoff/partial-availability correctness issue found in owner code review (an opening-only constituent could drag the whole comparison down), fixed by ID-4.1 below |
| ID-4.1 | Corrective: `RelativeStrengthEngine`'s comparison cutoff was computed from any constituent with at least one canonical bar, not only constituents that can actually form a return — on the real snapshot this let opening-only market/sector indexes collapse EVERY stock's own otherwise-valid session return to unavailable. Fix comparable-constituent cutoff semantics only — no public contract change, no scoring/Decision/TradePlan change, no index M5 data repair | ✅ Owner approved 2026-08-29 — `_ConstituentSeries.can_form_return`; real-data re-audit on the production retrieval path: stock_return now 526/526 available (was 0/526 — an engine artifact, now resolved); sector/market/every pairwise comparison remain 0/526 (a genuine, now-isolated index M5 data limitation); full suite green (2,833 passed, 1 pre-existing skip). Recommendation: an index-M5 data-quality prerequisite before the next RS-dependent milestone |
| ID-5 | Core index M5 data-quality root-cause & remediation (per ID-4.1's recommendation) — data-foundation corrective, NOT a trading-methodology milestone. Seven parts: **ID-5A** (settled-session repair, owner-authorized), **ID-5B** (live current-session M5 semantics canary), **ID-5C** (Gap & Session-Open Context, parallel, independent of ID-5B), **ID-5D**/**ID-5D.1** (Relative Volume/RVOL Context Foundation, parallel, independent of ID-5B), **ID-5E** (Point-in-Time Candle Retrieval & Replay-Safety Foundation, parallel, independent of ID-5B), **ID-5F** (Point-in-Time Quote Retrieval & SessionContext Replay Safety, parallel, independent of ID-5B), **ID-5G**/**ID-5G.1** (Point-in-Time MarketSnapshot Retrieval Safety, parallel, independent of ID-5B) | ✅ **ID-5A owner-authorized, EXECUTED and CLOSED 2026-08-29** — real `run_settlement_repair()` run for the settled 2026-08-28 gap, 537/537 instruments succeeded, 0 failures; off-grid rows 60,410→0; market benchmark + all 8 sector indexes now 75/75 canonical; RelativeStrength sector/market/pairwise availability restored (204-526/526, matching real sector-mapping coverage); OR30 3/526→526/526 `COMPLETE`. ✅ **ID-5B OWNER APPROVED / CLOSED 2026-09-01** — final settled-provider classification accepted as `CASE_B_CONTENT_CHANGES`; no additional live canary required. 25 raw capture files across the frozen 5-instrument canary (`NSE:NIFTY 50`, `NSE:NIFTY BANK`, `NSE:NIFTY IT`, `NSE:RELIANCE`, `NSE:INFY`); no failed capture records; no off-grid provider timestamps observed; ID-5B.1 corrected classification so forming boundary-candle changes never count as CASE B/C; owner approved that correction. Owner-authorized settled comparison on 2026-09-01 found 18 forming-at-capture rows changed, 704 closed-at-capture rows stable by unique exact OHLCV mapping, 1 eligible closed-at-capture row with no exact settled OHLCV candidate (`NSE:NIFTY 50`, `13:55`, captured at `14:00:01`), 0 off-grid rows, and 0 ambiguous mappings. Evidence: `docs/research/ID-5B-LIVE-M5-SEMANTICS-CAPTURE-2026-08-31.md`. ✅ **ID-5C CLOSED / owner-approved 2026-08-29** — `athena.intraday.gap_engine.GapEngine`; new `GapContext` (previous-session-close→current-session-open), independent of ID-5B by construction (D1-only, zero M5); 19 new tests, real-data sanity check 526/527 available on the settled 2026-08-28 session; full suite green (2,853 passed, 1 pre-existing skip). 🔄 **ID-5D architecture/methodology ACCEPTED 2026-08-29 — not fully closed**: owner code review found two correctness/policy issues, fixed by **ID-5D.1** below. **ID-5D.1 Ready for review 2026-08-29** — Issue A (current-session window correctness): the comparison window is now the longest CONTIGUOUS prefix of today's own expected canonical grid from session open, not merely however many canonical bars happen to exist regardless of gaps — a missing slot stops the window, later-reappearing canonical bars can never retroactively extend it (non-vacuously proven, engine-level and against real settled 2026-08-28 data with an injected gap). Issue B (retrieval policy): the hardcoded 120-calendar-day retrieval lookback (which would have silently become an undisclosed rolling-baseline-cap policy once M5 history exceeded it) replaced with `repo.earliest_candle_ts()` — a new single indexed `MIN(ts_open)` repository primitive, confirmed via `EXPLAIN QUERY PLAN` to use a covering index, not a table scan; rolling-cap policy and corporate-action adjustment both explicitly OWNER_DEFERRED, not resolved by this milestone. 10 new tests (5 engine-level current-window tests, 4 repository `earliest_candle_ts` tests, 1 workflow-level retrieval-policy test proving inclusion of a real 238-day-old comparable session) plus the pre-existing 27; real-data replay on the settled 2026-08-28 session at 3 cutoffs: 526/527 available (unchanged), zero point-in-time violations, performance confirmed as 2 indexed queries per instrument (was 1; the added `earliest_candle_ts` seek); mypy: the one ID-5D-introduced `calendar: CalendarEngine | None` narrowing error fixed locally via `cast()`, net mypy errors in `owner_validation.py` reduced from 25→24 (zero new). Full suite green (2,890 passed, 1 pre-existing skip). ✅ **ID-5E CLOSED / owner-approved 2026-08-30** — `list_candles_recent(..., as_of=...)` market-time point-in-time contract; the repeated ID-P0.1 "no `as_of` cutoff" limitation is now closed for candles (see ID-5E's own row below). ✅ **ID-5F CLOSED / owner-approved 2026-08-30** — same contract extended to `get_latest_quote(..., as_of=...)` (see ID-5F's own row below). 🔄 **ID-5G architecture ACCEPTED, ID-5G.1 Ready for review 2026-08-30** — same contract extended to `get_latest_snapshot_as_of(as_of)`, corrected in ID-5G.1 to full sub-second/offset precision (see ID-5G's own row below). Candle/quote/snapshot market-time retrieval are now all closed or ready, with full timestamp precision. ✅ **ID-5 OWNER APPROVED / CLOSED 2026-09-01**; ID-6 discovery architecture owner-approved with condition and ID-6A0 owner-approved/closed as of 2026-09-02 |
| ID-5E | Point-in-Time Candle Retrieval & Replay-Safety Foundation — infrastructure/correctness, not a trading methodology. Addresses the `list_candles_recent()`-has-no-`as_of` limitation carried forward since ID-P0.1 | ✅ CLOSED / owner-approved 2026-08-30 — `SqliteRepository.list_candles_recent(..., as_of=None)`: SQL-level `ts_open<=as_of` cutoff applied BEFORE `ORDER BY ... LIMIT` (never a Python filter after), `as_of=None` byte-identical to pre-ID-5E behavior. Every production caller with an explicit `as_of` now passes it: the core D1 `candles_by_id` fetch, its index/sector/VIX fallback reads, and confluence's M5/M15 reads (cross-session-reach methodology unchanged) in `owner_validation.py`; `opportunities_service._historical_change_pct`'s identical anti-pattern fixed the same way. `get_candles`/`candles_for_instruments` audited, already safe (explicit upper bound); `earliest_candle_ts` (ID-5D.1) audited, needs no `as_of` (lower bound only). MARKET-TIME safety only — knowledge-time/bitemporal replay, quote history, market snapshot, institutional-flow/universe-membership/config-version replay all identified as remaining gaps, not solved. 24 new tests (12 repository contract tests, 2 non-vacuously-proven pipeline invariance tests — a real D1 SMA(20) became `999999` before the fix, a real confluence signal flipped to unavailable before the fix); full suite green (2,903 passed, 1 pre-existing skip); zero new mypy failures. The repeated ID-P0.1 candle-replay limitation is now CLOSED |
| ID-5F | Point-in-Time Quote Retrieval & SessionContext Replay Safety — narrow infrastructure/correctness, not a trading methodology. Closes the one remaining candle-adjacent gap ID-5E's own caller audit found (`get_latest_quote()` has no `as_of` cutoff) | ✅ CLOSED / owner-approved 2026-08-30 — quote-history retention CONFIRMED (composite `PRIMARY KEY (instrument_id, ts)`, append-only) — feasibility gate passed, no schema migration needed. `SqliteRepository.get_latest_quote(..., as_of=None)`: same market-time contract as ID-5E (`AND ts<=?` before `ORDER BY ts DESC LIMIT 1`, never fetch-then-Python-reject). Sole production caller (`session_stage`'s `SessionContext.latest_quote_ts`) now bounded; `QUOTE_UNAVAILABLE` freshness semantics completely unchanged. Snapshot replay audited and explicitly NOT solved (a bounded `get_latest_snapshot_before` sibling already exists, unused — documented as a future milestone's head start, since closed by ID-5G below). 12 new tests, 2 non-vacuously proven at the pipeline level (`latest_quote_ts` leaked a future quote's timestamp before the fix); full suite green (2,915 passed, 1 pre-existing skip); zero new mypy failures |
| ID-5G | Point-in-Time MarketSnapshot Retrieval Safety — final narrow infrastructure/correctness milestone in the ID-5E/5F/5G sequence, not a trading methodology. Closes the `MarketSnapshot` gap ID-5E/5F's own audits identified | 🔄 **ID-5G architecture/scope ACCEPTED 2026-08-30 — not fully closed**: owner code review found a timestamp-precision correctness issue in the actual SQL, fixed by **ID-5G.1** below. Snapshot-history retention CONFIRMED (`PRIMARY KEY (ts)`, `ON CONFLICT(ts) DO NOTHING`) — feasibility gate passed. Audit found `_resolve_snapshot`'s single `get_latest_snapshot()` call feeds BOTH `RegimeEngine` and `MarketHealthEngine` — both genuinely analytical, both now bounded via a new, explicitly-named `get_latest_snapshot_as_of(as_of)` (INCLUSIVE `<=` boundary, evidence-based per §3, NOT an overload of `get_latest_snapshot_before`'s own STRICT `<` semantics, which stays untouched for its 2 real "prior state" callers). **ID-5G.1 Ready for review 2026-08-30** — owner found `datetime()`-wrapped SQL (chosen in ID-5G for offset safety) also TRUNCATES to whole seconds, so a same-second future snapshot could appear eligible; confirmed empirically (`datetime('...900+05:30') <= datetime('...100+05:30')` evaluates true). `julianday()` measured as an alternative — offset-safe, millisecond-safe, but demonstrably NOT microsecond-safe, rejected since production `as_of`/snapshot `ts` carry microsecond resolution (`datetime.now()`). Fixed via a Python-side full-precision comparison over every persisted row (measured 1,872 rows / ~13ms in the real production database) using aware-`datetime` ordering — zero floating-point loss at any sub-second granularity, correct across mixed offsets by construction. `get_latest_snapshot_before` shared the identical bug (adjacent fix, same helper, STRICT `<` unchanged); `get_latest_snapshot()`/`list_snapshots_recent()`'s own theoretical mixed-offset ordering risk reported, not fixed (no caller demonstrably needs it). 20 new tests total (12 ID-5G + 8 ID-5G.1), 3 non-vacuously proven at the pipeline level across both milestones; full suite green (2,935 passed, 1 pre-existing skip); zero new mypy failures. Candle (ID-5E), quote (ID-5F), and snapshot (ID-5G/ID-5G.1) market-time retrieval are now all closed with full precision; institutional-flow/universe-membership/config-version/knowledge-time replay remain explicitly unresolved |
| ID-6 | Discovery / scope and architecture freeze — determine what ID-6 should be from the live architecture and the completed ID-0→ID-5 evidence, especially the owner-approved ID-5B `CASE_B_CONTENT_CHANGES` result | ✅ **DISCOVERY ARCHITECTURE OWNER APPROVED WITH CONDITION 2026-09-02** — corrected design direction and architecture accepted, conditional on completing ID-6A0 before any ID-6A implementation. State, evidence finality/provenance, and confirmation remain orthogonal; current-session M5 remains provisional; and no irreversible ID-6 state may be caused directly or indirectly solely by live-M5-provisional evidence. No production qualification engine, persistence, UI, thresholds, Entry/TradePlan, ID-7, EM-6, EMR, DarvaX, or order behavior authorized. Evidence: `docs/research/ID-6-SCOPE-ARCHITECTURE-DESIGN.md` |
| ID-6A0 | Entry Qualification Architecture ADR — freeze the new persisted decision-relevant concept, advisory-only boundary, daily Decision vs intraday actionability separation, state/evidence-finality/confirmation orthogonality, live-M5 provisionality invariant, workflow-stage boundary, persistence/auditability principles, and owner-gated ID-6 implementation sequence | ✅ **OWNER APPROVED / CLOSED 2026-09-02** — ADR-013 accepted after ID-6A0.1 corrected evidence finality/provenance vs methodology confirmation. No production behavior was implemented in ID-6A0 |
| ID-6A | Entry Qualification Domain / State / Finality / Confirmation Contracts — introduce immutable ID-6A domain types only, bound to canonical Decision identity and preserving ADR-013's three orthogonal dimensions | ✅ **OWNER APPROVED / CLOSED 2026-09-02** — `EntryQualification`, state/finality/confirmation enums, structural reason-code enum, and minimal evidence-reference contract accepted under `athena.intraday`; no qualification engine, persistence, migrations, workflow stage, thresholds, UI, provider calls, DB writes, production behavior, ID-6B implementation, ID-7, EM-6, EMR, DarvaX, or order behavior implemented |
| ID-6B.0 | Entry Qualification Methodology / Engine Design — discovery, evidence analysis, methodology design, and deterministic-engine contract only; decide what the future pure ID-6B engine should do before implementation | ✅ **OWNER APPROVED / CLOSED 2026-09-02** — methodology report accepted at `docs/research/ID-6B-ENTRY-QUALIFICATION-METHODOLOGY-DESIGN.md`. Owner decisions frozen: `QUALIFIED` is architecturally permitted but no positive rule approved yet; `DISQUALIFIED_FOR_SESSION` is off for v0; OR15/OR30 are contextual/support only; WATCH and TRADE use the same intraday methodology unless evidence proves otherwise; `CONFIRMED_BY_POLICY` methodology remains unapproved; no additive score |
| ID-6B.1 | Entry Qualification Evidence Baseline & Policy Freeze — read-only settled historical market-time replay over real WATCH/TRADE candidates to measure ID evidence availability, prevalence, combinations, timing, overlap, and persistence before freezing v0 policy | ✅ **OWNER APPROVED / CLOSED 2026-09-02** — reusable read-only harness `athena.data.id6b1_entry_qualification_baseline` created; 5 consecutive recent sessions × 6 checkpoints × capped WATCH/TRADE candidates produced 370 candidate-checkpoint observations across 32 instruments. Artifacts: `artifacts/research/id6b1/id6b1_summary.json`, `artifacts/research/id6b1/id6b1_observations.jsonl`; stable analysis SHA-256 `7baf33e01df22d2acae000c44bcb7b0be0f2017d12248432e435eb986619b5fb`. Owner accepted the baseline but did not freeze v0 policy — the `EXPECTED_BAR_MISSING`=72.97% blocker was escalated to ID-6B.1A |
| ID-6B.1A | Session Data Quality & Baseline Representativeness Audit — root-cause `SessionDataQualityStatus.EXPECTED_BAR_MISSING` (270/370, 72.97%), verify checkpoint-boundary/harness correctness, and re-run the baseline uncapped to test representativeness | ✅ **OWNER APPROVED / CLOSED 2026-09-02** — root cause: chronic, systemic M15 candle off-grid condition (only the session's opening bar is reliably on-grid; `live_m5_settlement_repair.py` is M5-only, no M15 equivalent exists) accounts for 260/270 (96.30%) of `EXPECTED_BAR_MISSING` cases; confirmed by source inspection that VWAP/RS/RVOL/Gap/OR15/OR30 have ZERO M15 dependency, so the blanket gate is stricter than what the proposed v0 rule actually needs. Checkpoint-boundary math verified exact (no off-by-one, no harness bug). Uncapped replay (7,144 observations, 19x the original sample, same 5 sessions/6 checkpoints) found every headline prevalence figure broadly stable except TRADE-specific figures. Owner ratified Option C (artifact-owned availability) instead of the blanket `SessionDataQuality` gate |
| ID-6B.1B | Quality-Adjusted Policy Baseline & Wider TRADE Audit — apply Option C correctly, audit the trend contract at component level, and re-measure the candidate v0 policy over a materially wider TRADE-representative window | ✅ **OWNER APPROVED / CLOSED 2026-09-02** — trend-contract audit confirmed aggregate `BULLISH` already requires genuine M5+M15 agreement (`_aggregate_trend` source), so no correction to `candidate_policy_match`'s own formula was needed. Defined a research-only quality-adjusted evaluability contract; applying it to both the original 7,144-obs window and a fresh, deterministically-selected wider window (10 consecutive sessions, 2026-08-14–08-27, 17,082 observations, 4.8x more TRADE observations across 9 sessions vs. the original's 2) found evaluability stable at 99.55%–100% and M15 causing non-evaluability in <=0.03% of every sample — classified **NON-BLOCKING TECHNICAL DEBT**. WATCH vs. TRADE show a uniform prevalence shift (TRADE a few points higher on every field) with no structural divergence — single shared methodology preserved. Report: `docs/research/ID-6B.1B-QUALITY-ADJUSTED-POLICY-BASELINE.md`. Owner froze the v0 readiness methodology (VWAP positive AND aggregate trend BULLISH AND (RS support OR RVOL support)) and authorized ID-6B.2 |
| ID-6B.2 | Entry Qualification Pure Engine — implement ONLY the pure deterministic engine and its direct policy/reason contracts for the owner-frozen v0 methodology; no persistence, no workflow, no API/UI | ✅ **OWNER APPROVED / CLOSED 2026-09-02** — `EntryQualificationEngine.evaluate()` (`src/athena/intraday/entry_qualification_engine.py`): deterministic, side-effect-free, O(1), zero repository/provider/DB/wall-clock/workflow dependency. Implements the frozen v0 expression via explicit tri-state (TRUE/FALSE/UNKNOWN) AND/OR so missing evidence never collapses to bearish. State precedence: non-WATCH/TRADE or non-trading-session → `OUT_OF_SCOPE`; closed session → `EXPIRED`; pre-open → `NOT_YET` (evidence not yet expected); regular session → evaluate the frozen expression → `QUALIFIED`/`NOT_YET`/`UNKNOWN`. `DISQUALIFIED_FOR_SESSION` never emitted (exhaustive sweep-tested); confirmation always `NOT_EVALUATED`; `SessionDataQuality`/`EXPECTED_BAR_MISSING` never used as a blanket gate (Option C, test-proven); OR15/OR30/Gap/Sector proven not to affect state; WATCH/TRADE share one methodology, canonical type preserved. `evidence_finality` is an explicit, orthogonal caller input (provenance inference remains a future ID-6C/ID-6D concern per ADR-013). Extended `EntryQualificationReasonCode` minimally with 10 v0-methodology reason codes. Owner review found one safety-critical input-coherence gap, corrected and closed under ID-6B.2A |
| ID-6B.2A | Entry Qualification Input Coherence Hardening — prove Decision/SessionContext/IntradaySignalSet describe one coherent point-in-time candidate before evidence is read; contract hardening only, not a methodology change | ✅ **OWNER APPROVED / CLOSED 2026-09-02** — `_validate_input_coherence`/`_validate_nested_artifact_coherence` (`src/athena/intraday/entry_qualification_engine.py`), called unconditionally at the top of `evaluate()` before any branching. Requires exact equality (no tolerance) of instrument_id, session_date, and as_of between `SessionContext` and `IntradaySignalSet` (confirmed by source inspection to be the real, already-followed production contract), plus instrument/session_date/as_of coherence for the two externally-supplied v0-consumed nested artifacts (`relative_strength`, `relative_volume`) — `trend` needs no separate check (structurally guaranteed consistent by `IntradayAnalyticsEngine.assess`'s own construction) and `vwap` carries no identity fields. A mismatch raises `ValueError` deterministically, never `UNKNOWN`/`NOT_YET` (a contract violation is not a market state). Decision/SessionContext instrument fallback (`Decision.instrument_id=None`) preserved. Option C, frozen methodology, WATCH/TRADE parity all unchanged and regression-tested. Current/non-superseded Decision selection explicitly documented as a caller/workflow responsibility deferred to ID-6D — not solved here. 10 new focused tests (all non-vacuous — 3 mutation-verified) added to the existing 46, all 56 passing. No persistence, workflow, API, UI, ID-6C/ID-7/EM-6/EMR/DarvaX touched |
| ID-6C | Entry Qualification Persistence — durable, auditable, append-only persistence for the EntryQualification observations the closed ID-6B.2/2A engine already concludes; no methodology change, no workflow wiring, no API/UI | ✅ **OWNER APPROVED / CLOSED 2026-09-02** — new `entry_qualifications` table (SCHEMA_VERSION 16→17, `src/athena/data/store/schema.py`), FK-bound to `decisions(decision_id)`, mirroring `decision_traces`/`trade_outcomes` conventions exactly. Composite primary key `(instrument_id, session_date, as_of, decision_id, methodology_version)` is the append-only logical/idempotency identity. `SqliteRepository.save_entry_qualification` is idempotent and fails loudly on a genuinely conflicting payload. Read API: `get_entry_qualification`, `latest_entry_qualification_for_decision`, `latest_entry_qualification_for_instrument_session`, `list_entry_qualifications_for_instrument_session`. Owner review found one integrity gap (FK proves the Decision exists but not that the EntryQualification's Decision-derived fields agree with it) — see ID-6C.1 |
| ID-6C.1 | Entry Qualification Canonical Decision-Binding Hardening — prove every persisted EntryQualification's Decision-derived fields (decision_type, run_id, cycle_id, instrument_id) truthfully agree with the canonical Decision it references; integrity correction only, not a persistence-architecture change | ✅ **OWNER APPROVED / CLOSED 2026-09-02** — `_validate_entry_qualification_decision_binding` (`src/athena/data/store/repository.py`), called on every `save_entry_qualification` call (insert AND idempotency-check paths — an already-persisted valid row can never let a Decision-inconsistent second call hide behind "identical identity ⇒ no-op"). Requires exact equality of `decision_type`/`run_id`/`cycle_id`, and `instrument_id` only when `decision.instrument_id is not None` — mirroring `EntryQualificationEngine._resolve_instrument_id`'s own established fallback exactly (confirmed: real production `DecisionEngine` always sets `instrument_id` for WATCH/TRADE). Missing `decision_id` now raises a clean repository-level `RepositoryError` before any INSERT; the schema FK remains as a DB-level backstop (test-proven still enforced via a bypass). Corrected the `run_id`/`cycle_id` idempotency-exclusion rationale: they are excluded from the conflict-payload comparison because binding validation already proved them equal to the canonical Decision, not because they may legitimately differ — a same-`decision_id`-different-`run_id` write now fails loudly instead of returning a false idempotent no-op. SCHEMA_VERSION unchanged (17) — no DDL change required. Replaced 1 stale test, added 10 new (7 net), all non-vacuous, 2 mutation-verified (including an ordering-specific proof that binding validation runs before, not after, the idempotency check). No methodology, workflow, API/UI, schema, EMR, or DarvaX changes |
| ID-6D | Entry Qualification Workflow Integration & Provenance Resolution — wire the closed ID-6A–ID-6C.1 Entry Qualification chain into the canonical runtime for the first time; resolve current-Decision selection and evidence-finality honestly; no new methodology, no API/UI | ✅ **OWNER APPROVED / CLOSED 2026-09-02** — new `entry_qualification` `WorkflowStage` in `OwnerValidationPipeline` (`depends_on=("decision","intraday_analytics")`, declared last, proven not to perturb the ten pre-existing stages' order). "Current Decision" = exactly the Decision `dec_stage` just produced this same synchronous cycle (closure-captured, not re-queried) — provably freshest, no TTL/age heuristic invented. Engine called unconditionally (already self-handles non-WATCH/TRADE via `OUT_OF_SCOPE`); persistence scoped to WATCH/TRADE only. New pure `resolve_evidence_finality` (`src/athena/intraday/entry_qualification_provenance.py`) reuses the engine's own public structural/lifecycle eligibility gate (decision_type WATCH/TRADE AND `SessionPhase.REGULAR`) — never the tri-state formula — to determine `LIVE_M5_PROVISIONAL` vs `UNKNOWN_PROVENANCE`; source-verified all four direct readiness families are M5-derived. `NO_DECISIVE_PROVISIONAL_M5_DEPENDENCY` is structurally unreachable (ADR-013's own documented Decision-provenance insufficiency) — reported honestly, not faked. Owner review found `persisted_at=ctx.as_of` wrongly conflated evaluation time with write time — see ID-6D.1 |
| ID-6D.1 | Entry Qualification Persistence-Time Semantics — stop conflating `EntryQualification.as_of` (evaluation/market-time checkpoint) with `persisted_at` (actual durable-write instant); timestamp-semantics correction only, no workflow/methodology/Decision-selection/finality change | ✅ **OWNER APPROVED / CLOSED 2026-09-02** — ID-6D is now fully closed — audited existing clock conventions first (no injectable wall-clock abstraction existed; found the established per-module `utc_now()`/`_utc_now()`/inline `datetime.now(tz=UTC)` pattern in `portfolio/sync.py`/`darvax/screening/sweep.py`/`explosive_move/store/repository.py`, plus `SqliteRepository.set_ops_meta`'s own optional-injectable-timestamp precedent). `save_entry_qualification`'s own `persisted_at` parameter was already correctly designed (ID-6C) — the defect was the caller. Added an injectable `OwnerValidationPipeline(..., persistence_clock: Callable[[], datetime] | None = None)`, defaulting to `datetime.now(tz=timezone.utc)`; the stage now calls `persisted_at=self._persistence_clock()`, never `ctx.as_of`. Idempotent retry preserves the original `persisted_at` (test-proven with genuinely different injected clock values across two full pipeline executions). Latest-lookup ordering reconfirmed `as_of`-only, never `persisted_at` (test-proven with `as_of`/`persisted_at` in deliberately opposite relative order). Pure engine remains structurally clock-free. SCHEMA_VERSION unchanged (17) — no DDL needed, `persisted_at` column already existed. 4 new focused tests, 1 mutation-verified (reverting to `ctx.as_of` correctly failed the new distinct-timestamp and idempotent-retry tests). Full repository suite: 3,131 passed, 1 pre-existing skip. No methodology, Decision-selection, finality, schema, API/UI, EMR, or DarvaX change |
| ID-6E | Entry Qualification Replay & Shadow Validation — validate the frozen ID-6A–ID-6D.1 capability across deterministic historical replay (real engine) and persisted shadow observations; validation only, no methodology/threshold/API/UI change | 🔄 **HISTORICAL REPLAY VALIDATION OWNER-ACCEPTED (CLASSIFICATION: BEHAVIORALLY SOUND); SHADOW VALIDATION OPEN 2026-09-03** — new read-only harness `src/athena/data/id6e_replay_shadow_validation.py` reuses ID-6B.1's own `ReadOnlyStore`/`candidates_at` unmodified but calls the real, closed `EntryQualificationEngine.evaluate()`/`resolve_evidence_finality()` (never re-derives the v0 formula). Replayed the identical ID-6B.1B window (10 sessions, 17,082 observations) for direct comparability: state distribution 76.17% NOT_YET / 21.70% QUALIFIED / 2.13% UNKNOWN; QUALIFIED prevalence and WATCH 19.93%/TRADE 24.17% split match ID-6B.1B's research-formula figures almost exactly. All invariants hold, 0 harness defects, 100% LIVE_M5_PROVISIONAL finality (as expected for this WATCH/TRADE REGULAR-phase sample). Option C/M15 reconfirmed at full scale. Owner accepted the historical replay validation as behaviorally sound after ID-6E.1's Decision-episode trajectory correction (see below); shadow validation remained open only because the production schema was not yet activated — see ID-6E.2 |
| ID-6E.1 | Decision-episode trajectory-identity correction for ID-6E's transition/flicker and qualification-duration analysis — analytical correction only, no methodology/runtime change | ✅ **OWNER APPROVED / CLOSED 2026-09-02** — `_transitions`/`_qualified_duration` in `id6e_replay_shadow_validation.py` now group by `(instrument_id, session_date, decision_id)` instead of `(instrument_id, session_date, decision_type)`, ordered by the semantic `as_of` timestamp instead of the checkpoint label; a new descriptive `_decision_supersession` audit reports how often a symbol/session changes canonical Decision identity across checkpoints (3,401 instrument/session groups observed, 3,210 (94.4%) with more than one distinct Decision, 14,699 total distinct Decision episodes — mostly WATCH→WATCH/TRADE→TRADE renewal with 747 WATCH→TRADE and 806 TRADE→WATCH transitions). Corrected replay against real `db/athena.db` (17,082 observations, 0 defects, unchanged): multi-checkpoint Decision episodes 1,833 (was 3,755 instrument/session/type groups under the old, over-merged grouping); corrected flicker (qualified-then-later-not-qualified) 215 episodes = **11.73%** (was 1,493 groups = 39.76%) — the prior figure is superseded, root-caused to merging multiple canonical Decision episodes of the same type into one trajectory. Audited ID-6B.1B's own `_transitions` and confirmed it groups by `(instrument_id, session_date, decision_type)` too — the same defect predates ID-6E, inherited from a research-only contract written before ID-6C's Decision-binding persistence discipline existed; ID-6B.1B's own artifacts were not modified. All point-observation invariants confirmed byte-for-byte unchanged. New deterministic digest (`d18c2cb1c43688804c7aea8430b1d4a1539c48f4b3cab3e2a05fd2bba8a70ef9`) matches exactly across two independent full reruns. Owner approved: historical replay validation classified BEHAVIORALLY SOUND. Combined ID-6A–ID-6E Entry Qualification suite 194 passed, full repository suite 3,154 passed, 1 pre-existing skip |
| ID-6E.2 | Production Entry Qualification schema activation & shadow canary — operational activation only, no methodology/engine/workflow/schema code change | ✅ **ACTIVATION COMPLETE — SHADOW ACCUMULATION STARTED 2026-09-03** — preflight against real `db/athena.db` found SCHEMA_VERSION already 17 with `entry_qualifications` present (0 rows) — migration had already occurred via ATHENA's own routine, idempotent `SqliteRepository.initialize()` calls (`_open_repo()`/API startup); no ad-hoc SQL issued. Integrity-verified, checksummed safety backup taken (`db/backups/athena-pre-id6e2-shadow-canary-20260903T024201Z.db`, SHA-256 `42c1ecb2...`). Structural verification against a fresh v17 reference schema: 0 drift (28/28 tables, 56/56 indexes, exact `entry_qualifications` column/PK/FK/index match). Idempotency reconfirmed via an explicit second `initialize()` call (structural no-op). The already-running, already-scheduled production server fired its own PREMARKET cycle (08:15:29 IST) on its own schedule — no manual trigger — persisting **165 genuine `EntryQualification` rows** through the normal `OwnerValidationPipeline` runtime path. Full-population integrity audit: 0 Decision-binding mismatches, 0 orphaned decisions, 0 timezone/session-date incoherence, 0 invariant violations. All 165 rows are `EXPIRED`/`UNKNOWN_PROVENANCE`/WATCH — read-only root-caused (no frozen code touched) to the cycle's 08:15 `as_of` falling before `config/market.nse.json`'s `preopen_start` (09:00), correctly classified `SessionPhase.CLOSED` by the frozen session engine — not a defect. Genuine persistence latency observed for the first time: median 550.77s, p90 552.58s, max 553.12s, 0 negative. Evidence sufficient to prove runtime persistence operational, not yet sufficient for behavioral shadow characterization (single CLOSED-phase moment, no REGULAR-phase/QUALIFIED/NOT_YET/UNKNOWN/TRADE observation yet). Full record: `docs/ops/ID-6E2-ENTRY-QUALIFICATION-PRODUCTION-SCHEMA-ACTIVATION.md`. No new production code; full repository suite 3,190 passed, 1 pre-existing skip |

**ID-0 headline findings (full detail in the report):** (1) `intraday_candles()`
is genuinely live across all six runtime flows and already reaches
`ScoringEngine` (VWAP-reclaim + 5m/15m confluence bonuses) — narrower than
assumed (never reaches `RegimeEngine`/`DecisionEngine`-direct/`TradePlan`),
but not dormant as an earlier review suggested. (2) ADR-003's documented
`PipelineContext`/`ContextDelta`/`IntelligenceModule` contract is entirely
dormant (zero non-test callers); the live pipeline runs on a different,
undocumented-as-canonical mechanism (`runtime.workflow.WorkflowContext`/
`WorkflowStage`) — needs an explicit owner decision before ID-1 adds new
stages. (3) Sector Health is computed live every cycle but never threaded
into scoring/evidence/decision at three specific call sites in
`owner_validation.py` — already a named, deferred milestone (SD-3), not a
bug, and a hard prerequisite for the proposed `RelativeStrengthContext`
artifact. One documentation staleness found: `ATHENA-WORKFLOW-METHODOLOGY.md`
still states FAST runs every 5 minutes / 400 symbols; live config has been
10 minutes / 150 symbols since a 2026-08-10 incident-driven scale-back.

**ID-1 summary (full detail in the Milestone Review Summary given to the
owner in-chat, 2026-08-29):** new `athena.session` package
(`SessionContextEngine`, `SessionContext`, `TimeframeProvenance`,
`SessionPhase`, `SessionDataQualityStatus`) — a deterministic,
calendar/config-derived (never invented-window) intraday foundation.
Completed-candle semantics (`is_candle_completed`/`latest_completed_candle`)
guarantee a forming bar can never leak into "latest completed" reads.
Missing-bar detection reuses the existing `data/validation/calendar_expectations.py`
contract rather than inventing a parallel gap scheme. Wired as a genuine,
live, additively-declared `WorkflowStage` (`session`, no `depends_on`,
nothing depends on it) inside `OwnerValidationPipeline._scan_eligible` —
proven not to perturb the pre-existing six stages' topological order.
Existing VWAP/confluence/scoring/confidence/risk/Decision/TradePlan
behavior is unchanged (the full pre-existing regression suite, unmodified,
still passes). No persistence added — `SessionContext` is fully
reconstructable from already-canonical data, same as regime/market health.
No ADR required — squarely within ADR-003 Amendment 1's already-approved
canonical pattern. No signal, no gate, no threshold, no EntryQualification
yet.

**ID-2 summary (full detail in the Milestone Review Summary given to the
owner in-chat, 2026-08-29):** new `athena.intraday` package
(`IntradayAnalyticsEngine`, `IntradaySignalSet`, `IntradayTrendContext`,
`VwapEvidence`/`VwapRelation`, `TimeframeTrendEvidence`/`IntradayTrendLabel`)
— an analytical evidence container, explicitly not a trade signal (no
BUY/SELL/probability field exists anywhere on the contract, checked
structurally by test). Computes nothing new: formalizes the exact
`vwap`/`confluence` objects `ind_stage` already produced for
`ScoringEngine` this cycle (proven identical by Python object identity,
not just equal values), so there is no second, possibly-diverging
"VWAP relation" in the system. Aggregate `IntradayTrendLabel`
(BULLISH/BEARISH/NEUTRAL/UNKNOWN) is a zero-new-weights unanimous-vs-split
read of the existing 5m/15m confluence booleans — disagreement is reported
as NEUTRAL with both sides visible, never hidden behind a single number.
Reuses ID-1's `SessionContext`/`SessionDataQualityStatus` for precise
UNKNOWN explanations (e.g. citing the real `EXPECTED_BAR_MISSING`/
`TIMEFRAME_UNAVAILABLE` reason) rather than a generic "insufficient data"
message. Wired as a genuine, live `WorkflowStage`
(`intraday_analytics`, `depends_on=("session", "indicators")`) — proven
not to perturb the other seven stages' relative execution order, and
proven that scoring/confidence/risk/decision do not (yet) depend on it.
No persistence added — same reconstructable-from-canonical-data reasoning
as `SessionContext`. No ADR required. No ORB/gap/RVOL/relative-strength/
EntryQualification implemented — explicitly deferred to future ID-3+
milestones per the owner's own scope.

**ID-2.1 summary (full detail in the Milestone Review Summary given to the
owner in-chat, 2026-08-29):** owner code review of ID-2 found that
`ind_stage`'s `intraday_cs`/`fifteen_min_cs` — the candle series feeding
VWAP and 5m/15m confluence direction — were still `repo.list_candles_recent()`'s
**raw** result, never filtered through ID-1's own
`ts_open + duration <= as_of` completed-candle rule, even though
`SessionContext` already computed exactly that boundary for the same
candles. Fixed by adding one new, single-authority primitive,
`athena.session.completed_candles()` (the list-returning sibling of
`latest_completed_candle`, both now sharing one implementation), and
filtering both `intraday_cs` and `fifteen_min_cs` through it before any
VWAP/confluence use — input-time correctness only; the VWAP formula,
confluence SMA periods (9/5), and the `+10` max confluence bonus are all
byte-for-byte unchanged. Proven non-vacuously: a crafted extreme forming
candle is shown to have exactly zero effect one second before it
completes and a real, deterministic effect at the exact completion
boundary (verified by temporarily reverting the fix and confirming the new
tests fail, then restoring it). Two pre-existing confluence tests needed
their fixture's `as_of` moved later in the session (their assertions
unchanged) — the fixtures had implicitly assumed the pre-fix "raw candles
always count" behavior, which was exactly the bug. Also renamed the
disagreement trend label `NEUTRAL` → `MIXED` (owner decision: "neutral"
could misread as price structure itself being flat, when what's actually
known is that the two timeframes disagree) — no consumer depended on the
old name. No ORB/gap/RVOL/EntryQualification/new threshold introduced.

**ID-3 summary (full detail in the Milestone Review Summary given to the
owner in-chat, 2026-08-29):** new `OpeningRangeEvidence`
(`athena.intraday.opening_range_engine.OpeningRangeEngine`) — OR15/OR30 as
two parallel, non-competing evidence windows (no preference/score/winner
between them). Range boundaries anchor to `SessionContext.session_open_ts`
(never a hardcoded 09:15 — proven against a real special session).
Formation status (`FORMING`/`COMPLETE`/`INCOMPLETE_DATA`/`NOT_AVAILABLE`/
`NOT_APPLICABLE`) distinguishes "window still running" from "window's time
elapsed but a real bar is missing" — never silently treats a partial range
as final. Current relation (`ABOVE`/`BELOW`/`INSIDE`/`AT_HIGH`/`AT_LOW`)
is a snapshot; breakout/breakdown is a separately-modelled, non-repeating
TRANSITION (the first observed crossing only — proven non-vacuously that
a still-forming candle cannot alter either). Raw measurements only
(`bars_since_breakout`, extension percentages, `returned_inside_range`) —
no STRONG/WEAK/FAILED label, no confirmation buffer, no volume-confirmed
breakout. Raw opening-range volume recorded; RVOL explicitly still
deferred (real 5m history remains ~25 sessions deep — thin for a
time-of-day baseline, per ID-2's own finding). Extends the existing
`intraday_analytics_stage` (no new `WorkflowStage`) since it already
produces `IntradaySignalSet`; still no dependency from
scoring/confidence/risk/decision onto any of this. A read-only real-data
sanity check (scratch copy of `db/athena.db`, never the original) found a
genuine, precisely-diagnosed limitation: on that snapshot's most recent
real day, every one of 537 real instruments had 100-130 real `5m` rows in
that single session (vs. the canonical ~75), pushing the session's own
clean opening bars out of the `limit=100` fetch shared with VWAP/
confluence/session before OR15/OR30 ever saw them — a diagnostic run with
a larger, test-only limit resolved OR15/OR30 to `COMPLETE` for 526/527 real
instruments, confirming the algorithm itself is correct and the fetch
limit is the actual constraint. Not changed here — a shared limit
affecting four consumers is a real decision, not a one-snapshot tuning call.

**ID-3.1 summary (full detail in the Milestone Review Summary given to the
owner in-chat, 2026-08-29):** owner code review of ID-3 found two production
correctness issues. (A) The `limit=100` fetch ID-3's own sanity check found
is not a safe "give me this session" contract — fixed by bounding session-
scoped reads (`session_stage`, `ind_stage`'s VWAP fetch,
`intraday_analytics_stage`'s ORB fetch) to `[session_day_start(as_of, tz),
as_of]` via the repository's existing `get_candles()` (no new repository
method needed — it already had exactly the required bounded, indexed,
ascending-order semantics); new `athena.session.session_day_start()`
computes the bound. Confluence's own 5m/15m fetches were audited and
deliberately left unchanged (its rolling SMA genuinely reads across a
session boundary early in the day today — reported as an open methodology
question, not silently redefined). (B) `OpeningRangeEngine` judged range
completeness by comparing raw in-window row count against expected count,
so an off-grid/unexpected timestamp could in principle substitute for a
genuinely missing canonical opening-range slot — fixed by filtering to
exact expected M5 slots (via the existing `expected_intraday_opens`
authority) once, up front, before formation/relation/breakout ever run; the
existing count comparison becomes correct by construction once its input
is pre-filtered. Both fixes proven non-vacuously (temporarily reverted,
confirmed the new tests fail, restored). A real-data acceptance check
against the production retrieval path (no test-only limit) found OR15
now resolves `COMPLETE` for 526/526 real candidates, while OR30 resolves
`COMPLETE` for only 3/526 — a real, previously-masked number (ID-3's own
"526/527 COMPLETE" diagnostic read was itself inflated by Issue B's
counting bug), traced to a real M5 timestamp-drift onset at the session's
6th canonical 5-minute slot (09:40) for 522/526 instruments. Full suite:
2,806 passed, 1 pre-existing skip.

**ID-4 summary (full detail in the Milestone Review Summary given to the
owner in-chat, 2026-08-29):** new `RelativeStrengthContext`
(`athena.intraday.relative_strength_engine.RelativeStrengthEngine`) —
point-in-time stock-vs-sector/market comparative performance, NOT RSI, not
a scoring input, not a market→sector→stock gating chain. Reuses the exact
market-benchmark identity `OwnerValidationPipeline._resolve_index_candles`
already resolves for regime and the exact `Instrument.sector` →
`sector_index_mapping.json` → `index_intelligence.json` chain
`SectorHealthEngine` already uses — no new benchmark config, no second
sector mapping. Common-cutoff design: one shared comparison window
(`comparison_start_ts`/`comparison_cutoff_ts`) across all three
constituents, never an asynchronous per-constituent endpoint; a
constituent's "opening reference" must be exactly the session's own open
instant, and its "closing" point is the latest of its OWN canonical bars
at-or-before the shared cutoff — never a later bar even when that
constituent itself has one further ahead (proven: a stock with bars
through 09:30 correctly still returns off its own 09:20 close when the
cutoff is capped there by a slower constituent). A same-bar (zero-duration)
comparison reports honestly unavailable rather than a fabricated return.
Both rules proven non-vacuously (temporarily reverted, confirmed the new
tests fail, restored). Sector/market unavailability never blocks an
otherwise-computable pair (`stock_vs_market` still resolves with no
sector mapping, and vice versa) — `UNKNOWN` is never substituted with
`MATCHING`. One new `WorkflowStage` (`relative_strength`, depends only on
`session`); `intraday_analytics_stage` gains it as a third dependency —
proven not to perturb the six pre-existing structural stages' order.
Market-benchmark and sector-index M5 series are fetched ONCE per run
(shared across the whole universe / each sector's stocks), not per stock.
A real-data audit (read-only, production retrieval path) found the market
benchmark and all 8 mapped sector indexes each have only 1/75 canonical M5
slots on the checked real session (worse than equities' own drift, which
stays clean through 5 slots) — the comparison cutoff at the time was
computed as the minimum across ALL constituents with any canonical bar,
which (owner review found, ID-4.1) let this opening-only index data
collapse `RelativeStrengthContext` to universally unavailable, including
stocks whose own data was perfectly fine. **Corrected in ID-4.1 — see
below; do not read this paragraph's original "0/526 universal collapse"
finding as a pure data limitation, it was substantially an engine
artifact.** Full suite: 2,825 passed, 1 pre-existing skip.

**ID-4.1 summary (full detail in the Milestone Review Summary given to
the owner in-chat, 2026-08-29):** owner code review of ID-4 found the
common-cutoff computation used ANY constituent with at least one
canonical bar, not only constituents that can actually form a return —
conflating data presence with return availability (an opening-only
constituent has a genuine session-open bar but no later one, so it can
never itself produce a return, yet its single timestamp was still allowed
to cap the shared window for every other constituent). Fixed with one new
property, `_ConstituentSeries.can_form_return` (opening exists AND a later
canonical bar exists) — `comparison_cutoff_ts` is now the minimum of only
comparable constituents' own latest bar (`None` if none are comparable).
`_return()` itself needed no change: once fed a correctly-computed cutoff,
its existing same-bar-unavailable logic already produces the right answer
for every constituent. No public contract change. Proven non-vacuously (6
of 8 new tests fail against the reverted fix). Real-data re-audit on the
identical production retrieval path/as_of as ID-4's own check now shows a
precise, dimension-level truth: **stock_return available for 526/526 real
candidates** (was 0/526 — the engine bug, now resolved) while
sector_return/market_return/every pairwise comparison remain 0/526 — a
genuine, now cleanly isolated index-M5 data-quality limitation (market
benchmark and all 8 sector indexes still opening-only; unchanged, not
touched here — no nearest-neighbor/resampling/forward-fill workaround
introduced). Recommendation: an index-M5 data-quality/remediation
prerequisite before the next RS-dependent or comparison-methodology
milestone, rather than proceeding directly into further signal
methodology while comparative evidence stays structurally unavailable.
Full suite: 2,833 passed, 1 pre-existing skip.

**ID-5 summary (full detail in the Milestone Review Summary given to the
owner in-chat, 2026-08-29):** audit-first, data-foundation milestone —
not a trading-methodology change, no code fix made. Traced ATHENA-core's
own M5 lifecycle (`KiteProvider._historical()` → ingestion → repository)
and found the root cause was already investigated and fixed once before:
a prior Owner/Chief-Architect-authorized repair
(`src/athena/data/live_m5_settlement_repair.py`, core `athena.data`, not
EMR — dated 2026-08-28) already corrected 1,051,481 off-grid M5 rows
across 537 instruments (market benchmark + all 8 sector indexes + 528
equities included) for 2026-07-28 through 2026-08-27, proving Kite's
historical API returns off-grid, provisional timestamps for not-yet-
settled recent data and clean grid-aligned data once a date genuinely
settles — `KiteProvider` itself applies zero transformation
(independently re-confirmed: `ts_open` comes straight from the raw Kite
response row, no `datetime.now()`/request-time substitution anywhere).
The ONE gap is 2026-08-28 itself, excluded from that run by explicit,
correct design (the tool never repairs "today," and 2026-08-28 WAS
"today" when it ran) — now a fully settled date. Independently
re-verified via a fresh read-only DB audit: already-repaired dates remain
perfectly clean (indexes included); 2026-08-28 shows the exact same
already-diagnosed shape (109 rows, 1/75 canonical, first off-grid
`09:43:55`) as every date the prior repair fixed. Root cause:
**PROVIDER_RETURNS_OFF_GRID_CURRENT_SESSION (Kite settle-lag), CONFIRMED**.
No index-vs-equity branching exists in ATHENA's fetch path — the two
share byte-identical code; index instruments simply settle later upstream
at Kite than equities do. Grep-confirmed zero EMR/DarvaX imports anywhere
audited. What remains genuinely open and NOT resolved here: Track B's
live provisional-vs-settled OHLCV-content question (built, unit-tested,
never executed — needs an open trading session; today is Saturday, next
is 2026-08-31) — a separate, already-tracked item, not blocking the
historical gap closure. Proposed action (not executed): backup + re-run
the existing, already-tested `run_settlement_repair()` for 2026-08-28 —
requires live Kite credentials and a real production write, so it was not
performed unilaterally; awaiting explicit owner authorization. 1 new test
added (`resolve_settlement_repair_dates` correctly targets the real gap
date); full suite 2,834 passed, 1 pre-existing skip.

**ID-5A execution summary (owner-authorized 2026-08-29, full detail in
IMPLEMENTATION_SUMMARY.md's "ID-5A" addendum):** backup taken and
integrity-verified first (`db/backups/athena-pre-m5-repair-20260828-gap-20260829T155925Z.db`,
checksummed); live Kite auth preflight passed; `run_settlement_repair()`
executed for the settled 2026-08-28 session across the exact prior
537-instrument scope — **537/537 succeeded, 0 failures, 0 retries**;
60,410 off-grid rows → 0; market benchmark and all 8 mapped sector
indexes now 75/75 canonical (were 1/75). RelativeStrength re-audit: sector/
market/every pairwise comparison, previously 0/526, now available for
204-526/526 (exactly the real sector-mapping coverage — no data left on
the table). OR30 3/526→526/526 `COMPLETE`. Full suite re-run:
unchanged, 2,834 passed. Real DB integrity re-verified post-write (`ok`,
0 FK violations). No ATHENA code touched. ID-5B (live current-session
semantics) not started — needs 2026-08-31.

**ID-5C summary (full detail in the Milestone Review Summary given to the
owner in-chat, 2026-08-29):** new `GapContext`
(`athena.intraday.gap_engine.GapEngine`) — previous-trading-session-close
→ current-session-open price transition, NOT an intraday return, NOT
gap-fill/-hold/-rejection/-continuation, zero-threshold `GAP_UP`/
`GAP_DOWN`/`FLAT`/`UNKNOWN` only. Audited existing gap-related code first
(`market_health.compute_gap_stability`, `regime.RegimeEngine._gap`, EM's
own internal `session_invariant_evidence.gap_pct`, dashboard-only
`_gap_detail`) — none reusable as a canonical per-instrument artifact, so
`GapContext` is genuinely new, but reuses the existing `(open -
prior_close)/prior_close*100` formula convention, not a new methodology.
Previous-session resolution reuses the existing
`latest_trading_day_on_or_before` calendar helper (zero new calendar
code) — proven against two real dates: 2026-08-31 Monday → 2026-08-28
Friday, and 2026-09-15 Tuesday → 2026-09-11 Friday (skipping the real
2026-09-14 Ganesh Chaturthi holiday). Both previous-close and
current-open are read from the instrument's own already-fetched D1
candle history (zero new repository reads, zero M5 dependency of any
kind) — a missing exact match is honestly unavailable, proven
non-vacuously that a stale older D1 candle can never silently
substitute. `GapEngine` itself is pure (no I/O). Composed into the
existing `session_stage` rather than a new `WorkflowStage` — no new
graph node/edge, so the existing Kahn-ordering proofs needed no update.
Independence from later M5 data (canonical, off-grid, forming) proven
non-vacuously. Real-data sanity check on the settled 2026-08-28 session:
526/527 real candidates resolve a real `GapContext` (367 `GAP_UP`, 135
`GAP_DOWN`, 24 `FLAT`; gap_pct −2.18% to +5.28%, median +0.19%). Full
suite: 2,853 passed, 1 pre-existing skip. ID-5B remains untouched and
separately gated on 2026-08-31.

**ID-5D summary (full detail in the Milestone Review Summary given to the
owner in-chat, 2026-08-29 — the current-window computation and the
retrieval bound described below were subsequently corrected by ID-5D.1;
see that summary immediately following this one):** new `RelativeVolumeContext`
(`athena.intraday.relative_volume_engine.RelativeVolumeEngine`) —
cumulative same-time-of-day relative volume ("is this stock trading more
or less volume today, through this exact point, than it typically does
through the same point?"), NOT a surge/spike label, zero-threshold
`ABOVE_BASELINE`/`BELOW_BASELINE`/`AT_BASELINE`/`UNKNOWN` only. Audited
existing volume-related code first (`IndicatorName.VOLUME_MA`,
`ScoringEngine._liquidity`, `market_health.compute_liquidity_aggregate`,
`OpeningRangeFormation.volume`) — none is a per-instrument historical
ratio, so `RelativeVolumeContext` is genuinely new; EMR's own
`REL_VOLUME_C` (hardcoded 20-session baseline) and DarvaX's
`volume_expansion` (5-bar/50-bar ratio) were audited for awareness only,
never imported (both remain TRACK_ISOLATED per ADR-010/ADR-012). Real
historical M5 depth measured at a hard ceiling of 23 trading days before
2026-08-28 (M5 ingestion begins 2026-07-28) — no baseline-length N is
hardcoded; the engine uses ALL available comparable prior sessions
instead, with `baseline_session_count`/`baseline_session_dates` exposing
full provenance. Same-time-of-day alignment is exact (a historical
session must have every one of its own first N canonical slots present,
never partial-credited); point-in-time safety is structural
(`if d >= session_date: continue`), verified non-vacuously at both the
engine level (reverting the alignment logic broke 4 tests) and the
workflow level (reverting the point-in-time guard changed
`baseline_session_count` from 1→2 and `rvol_ratio` from 2.0→1.333 in a
real pipeline cycle). Index volume directly queried and confirmed always
zero (`NSE:NIFTY 50`/`NSE:NIFTY IT`/`NSE:INDIA VIX`) — index RVOL
correctly reports unavailable, not fabricated. Wired into
`IntradaySignalSet`/`owner_validation.py` as a new `relative_volume`
`WorkflowStage` (depends only on `session`, its own bounded 120-calendar-day
lookback M5 read — a RETRIEVAL bound distinct from the baseline POLICY).
25 new engine tests + 2 new workflow-integration tests (ordering-proof,
real-cycle wiring proof). Real-data replay on the settled 2026-08-28
session at 3 cutoffs (early/mid/late): 526/527 available at every cutoff,
`baseline_session_count` uniformly 23, zero point-in-time violations;
`rvol_ratio` distribution (early cutoff) min 0.02/median 0.52/max 80.0.
Performance: exactly 1 repository query per instrument (single wide-range
read, indexed via `idx_candles_range`, confirmed by `EXPLAIN QUERY PLAN`),
935,449 total M5 rows read across 527 instruments × 3 cutoffs in 7.75s —
no N×M query-explosion pattern. Full suite: 2,880 passed, 1 pre-existing
skip. OWNER_PENDING: whether a rolling baseline-length cap should be
introduced once more than 23 trading days of M5 history accumulates (not
decided here — a future policy question, not a defect). ID-5B remains
untouched and separately gated on 2026-08-31.

**ID-5D.1 summary (full detail in the Milestone Review Summary given to
the owner in-chat, 2026-08-29):** correctness/policy correction only — no
RVOL methodology change (cumulative same-time-of-day semantics, arithmetic
mean, raw ratio, zero-threshold relations, no hardcoded baseline-length
cap, index-unsupported behavior all UNCHANGED). **Issue A (current-window
integrity):** the original ID-5D implementation counted every present
canonical current-session bar regardless of contiguity, so a missing
middle slot (e.g. 09:20 absent between present 09:15/09:25 bars) let the
current window silently drift out of same-time alignment with the
historical baseline's own first-N-slots comparison. Fixed by walking
today's own expected canonical grid from session open and stopping at the
first missing slot — the comparison window is now the longest CONTIGUOUS
prefix, never jumping over a gap, never extended by a canonical bar that
reappears later. `RelativeVolumeContext` remains genuinely available at
its own explicit `comparison_cutoff_ts` even long after real time has
moved past it (a true, dated measurement, not staleness — no freshness
threshold introduced). Verified non-vacuously: reverting to the old
count-all-canonical behavior failed 2 new tests with exact wrong values,
and a real-shape synthetic gap injected into real NSE:RELIANCE
2026-08-28 data (removing the real 09:35 candle) correctly stopped the
window at 09:30 instead of 10:05. **Issue B (retrieval policy):** the
original bounded M5 read used a hardcoded 120-calendar-day lookback,
which would have silently become an undisclosed rolling-baseline-cap
POLICY the moment M5 history exceeded 120 days — resolving the
OWNER_PENDING rolling-cap question without owner approval. Fixed by
adding `SqliteRepository.earliest_candle_ts(instrument_id, timeframe)` (a
single indexed `MIN(ts_open)` seek on the existing `idx_candles_range`
index, confirmed via `EXPLAIN QUERY PLAN` to use `SEARCH ... USING
COVERING INDEX`, not a table scan) and resolving the retrieval lower
bound from it instead. Verified non-vacuously: a real trading session
238 days before as_of (2026-01-05, beyond the old hardcoded bound) was
excluded from the baseline under the old retrieval and correctly included
under the corrected retrieval, in a real pipeline cycle. Both the
rolling-baseline-cap policy question and corporate-action volume
adjustment remain explicitly OWNER_DEFERRED — not resolved by this
milestone. 10 new tests (5 engine-level current-window tests in
`test_relative_volume.py`, 4 repository tests for `earliest_candle_ts` in
`test_repository.py`, 1 workflow-level retrieval-policy integration test
in `test_owner_validation.py`) on top of ID-5D's original 27. Real-data
replay on the settled 2026-08-28 session, corrected engine + corrected
retrieval, at the same 3 cutoffs: 526/527 available (unchanged),
`baseline_session_count` distribution min 23/max 24 (one instrument
gained one additional comparable session under the corrected retrieval),
zero point-in-time violations. Performance: 2 indexed repository queries
per instrument (was 1 — the added `earliest_candle_ts` seek), still no
N×M query-explosion pattern. One ID-5D-introduced mypy narrowing error
(`calendar: CalendarEngine | None`) fixed locally via `cast()`, scoped
only to this call site — `owner_validation.py`'s total mypy error count
went from 25 (with the ID-5D-introduced error) to 24 (matching its
pre-ID-5D baseline of 3 structurally-identical pre-existing instances for
other engines, left untouched, out of scope). Full suite: **2,890
passed, 1 pre-existing skip**, 0 failed. Ruff clean (7 pre-existing,
unrelated SIM117 findings elsewhere in `repository.py`, confirmed
present in the file before this milestone touched it). ID-5B remains
untouched and separately gated on 2026-08-31.

**ID-5E summary (full detail in the Milestone Review Summary given to the
owner in-chat, 2026-08-29):** infrastructure/correctness milestone, NOT a
trading methodology — addresses the `list_candles_recent()`-has-no-`as_of`
replay limitation carried forward since ID-P0.1. Audited every candle
retrieval API and its production callers first: `get_candles`/
`candles_for_instruments` already carry an explicit upper bound (safe by
construction); `earliest_candle_ts` (ID-5D.1) only resolves a lower bound
(safe, since the subsequent range read is still capped by `ctx.as_of`);
`list_candles_recent` had NO cutoff at all. Found the daily-indicator path
(`IndicatorEngine.compute_all`) has ZERO downstream protection against a
future-dated row (unlike M5/M15 confluence, already structurally shielded
by `completed_candles`'s own `as_of` filter) — confirmed via a real
pipeline run whose SMA(20) became `999999` the moment one future D1
candle entered the retrieval. Fixed by adding an optional keyword-only
`as_of: datetime | None = None` to `list_candles_recent`
(`as_of=None` preserves the exact pre-ID-5E behavior byte-for-byte); the
cutoff is applied in SQL `WHERE ts_open<=?` BEFORE `ORDER BY ... LIMIT`,
never as a Python filter after (the latter would let future rows steal
LIMIT slots from genuinely earlier rows — proven non-vacuously: a
before-cutoff Python-filter reverting attempt returned an empty result for
a cutoff planted deliberately mid-history). Every production caller with
an explicit analytical `as_of` in scope now passes it: the core D1
`candles_by_id` fetch and its index/sector/VIX fallback reads in
`OwnerValidationPipeline.run()`, confluence's own M5/M15 reads in
`intraday_analytics_stage` (the deliberate cross-session-boundary reach —
SMA(9)/SMA(5) drawing on yesterday's trailing bars — is completely
unchanged, only genuinely future-dated rows are now excluded), and
`opportunities_service._historical_change_pct`'s identical fetch-then-
Python-filter anti-pattern. Explicitly classified LIVE_CURRENT_STATE
(unchanged) vs EXPLICIT_AS_OF_ANALYTICAL (fixed) for every caller — dashboard
presentation reads (`market_history_service.py`, `market_summary_service.py`)
render the current live snapshot, not a historical replay, so were left
untouched. Two non-vacuous pipeline-level proofs: real D1 SMA(20) became
`999999` before the fix, restored after; a real confluence signal (5m
SMA(9) direction) flipped from a genuine bullish/bearish read to
`unavailable` once 240 future-dated M5/M15 noise rows crowded the real
bars out of the retrieval's own `limit=100` window before the fix,
restored after. 24 new tests (12 repository-level contract tests
covering the full §32 checklist — cutoff/no-cutoff/exact-boundary/
future-rows-cannot-consume-limit/ordering/timeframe-isolation/D1/empty-
before-all-data/cutoff-after-all-data/naive-rejection/query-plan; 2
pipeline-level invariance tests). Scope is explicitly MARKET-TIME
(`ts_open`) safety only — this schema does not track when a row was
actually persisted/known to ATHENA, so knowledge-time/bitemporal replay
remains unsupported and is not claimed solved; quote history
(`get_latest_quote`), market snapshot (`get_latest_snapshot`),
institutional-flow/candidate-universe-membership/config-version replay
are all identified as remaining gaps, explicitly out of this milestone's
scope (candle retrieval only), not silently solved or hidden. EMR/DarvaX
retrieval APIs audited for boundary awareness only, untouched (both
remain TRACK_ISOLATED). No trading methodology changed anywhere. Full
suite: **2,903 passed, 1 pre-existing skip**, 0 failed. Ruff clean (same 7
pre-existing, unrelated `repository.py` SIM117 findings). Mypy: zero new
failures across all three touched files (`owner_validation.py` stays at
24, `repository.py` stays at 10 pre-existing/unrelated errors,
`opportunities_service.py` stays at its own pre-existing 13). ID-5B
remains untouched and separately gated on 2026-08-31.

**ID-5F summary (full detail in the Milestone Review Summary given to the
owner in-chat, 2026-08-30):** narrow infrastructure/correctness milestone
closing the one remaining candle-adjacent gap ID-5E's own caller audit
identified — `get_latest_quote()` had no point-in-time cutoff, so
`SessionContext.latest_quote_ts` could still receive a future-dated quote
during a historical replay even with every candle input now bounded.
Quote-schema audit first: `quotes` table's `PRIMARY KEY (instrument_id,
ts)` already retains one row per distinct timestamp, append-only —
feasibility gate PASSED, no schema migration needed. Exactly one
production caller of `get_latest_quote` exists anywhere in
`src/athena/`: `session_stage`. Fixed the same way as ID-5E:
`get_latest_quote(instrument_id, *, as_of=None)`, `AND ts<=?` in SQL
before `ORDER BY ts DESC LIMIT 1`, never fetch-then-Python-reject (which
the milestone explicitly warned would hide a valid earlier quote behind
a later, ineligible one — proven non-vacuously: reverting to that exact
anti-pattern shape failed 4 of the 10 new repository tests). Session
stage now passes `as_of=ctx.as_of`; `SessionContext`'s own
`QUOTE_UNAVAILABLE` freshness methodology is completely untouched — only
the source of `latest_quote_ts` changed. Real pipeline proof: reverting
the production caller's fix let `latest_quote_ts` leak a future quote's
`09:40` timestamp instead of the real `09:20` one; restored, re-confirmed
invariant. `EXPLAIN QUERY PLAN` confirms `SEARCH quotes USING INDEX
sqlite_autoindex_quotes_1` (SQLite's own automatic PK index) — no new
index. Snapshot replay audited, explicitly NOT solved: a bounded
`get_latest_snapshot_before(before)` sibling API already exists in the
repository but is unused by the analytical caller — documented as a
concrete head start for a future narrow milestone, not acted on here.
Knowledge-time/bitemporal limitation unchanged from ID-5E. 12 new tests.
Full suite: 2,915 passed, 1 pre-existing skip. Zero new mypy failures.
ID-5B remains untouched and separately gated on 2026-08-31.

**ID-5G summary (full detail in the Milestone Review Summary given to the
owner in-chat, 2026-08-30):** final narrow infrastructure/correctness
milestone in the ID-5E/5F/5G sequence — closes the `MarketSnapshot` gap
those two audits identified. Schema audit: `market_snapshots`' `PRIMARY
KEY (ts)` plus `ON CONFLICT(ts) DO NOTHING` confirms history is retained
per distinct timestamp (feasibility gate passed) but also that a
same-timestamp correction attempt would be silently dropped — a genuine
knowledge-time limitation, documented not solved. Caller audit found
`_resolve_snapshot`'s single `get_latest_snapshot()` call feeds BOTH
`RegimeEngine` (via `_maybe_regime`) and `MarketHealthEngine` (via
`run()`'s own `enriched_snap`) — both genuinely analytical, unlike the
initially-suspected "write path only" framing. Fixed via a new,
explicitly-named `get_latest_snapshot_as_of(as_of)` — deliberately NOT an
overload of the already-existing `get_latest_snapshot_before(before)`,
whose own STRICT `<` semantics its two real callers (previous-trading-day
snapshot lookup, pre-decision snapshot lookup) genuinely need, and which
was left completely untouched. Exact-boundary choice (INCLUSIVE `<=`)
justified with evidence, not symmetry alone: matches every other ID-5
point-in-time contract's convention, matches `_resolve_snapshot`'s own
synthetic-snapshot construction at exactly `as_of`, and no existing caller
needs exclusion at this specific boundary. Timezone audit of the
file-based provider's `_aware_ts` found it accepts ANY UTC offset in a
persisted snapshot's `ts` (unlike candles/quotes, always uniformly
serialized) — so the new query deliberately keeps `datetime()`-wrapped SQL
(measured via `EXPLAIN QUERY PLAN`: a full table SCAN, not indexed) rather
than a faster raw-TEXT comparison, since `market_snapshots` holds only one
row per validation cycle and a full scan there costs nothing meaningful.
Non-vacuously proven at both the repository level (4 of 10 new tests fail
under a fetch-then-Python-reject revert) and the real pipeline level (a
spied `MarketHealthEngine`-bound `MarketSnapshot.india_vix` leaked a
future snapshot's extreme value before the fix, in both the
has-an-earlier-snapshot case and the only-a-future-snapshot case). 12 new
tests. Full suite: 2,927 passed, 1 pre-existing skip. Zero new mypy
failures. Candle (ID-5E), quote (ID-5F), and snapshot (ID-5G) market-time
retrieval are now all closed; institutional-flow publication timing,
candidate-universe membership, config-version replay, and knowledge-time/
bitemporal replay for all three retrieval kinds remain explicitly
unresolved. ID-5B remains untouched and separately gated on 2026-08-31.

**ID-5G.1 summary (full detail in the Milestone Review Summary given to
the owner in-chat, 2026-08-30):** narrow correctness repair on top of
ID-5G's accepted architecture — no methodology change. Owner code review
found ID-5G's `datetime()`-wrapped SQL (chosen for offset safety) also
TRUNCATES to whole seconds, so a same-second future snapshot could
appear eligible; confirmed empirically (`datetime('...900+05:30') <=
datetime('...100+05:30')` evaluates true in SQLite). `julianday()` was
measured as a candidate fix: offset-safe, and millisecond-safe (a full
0–999ms sweep produced zero ordering collisions), but demonstrably NOT
microsecond-safe (two `ts` values 1 microsecond apart evaluated as
float-equal) — rejected, since real production `as_of`/snapshot `ts`
values carry microsecond resolution (`datetime.now()`, confirmed via a
producer-precision audit of `KiteProvider`/`FileProvider`/
`owner_validation.py`'s own synthetic constructions). Fixed instead with
a Python-side full-precision comparison over every persisted row
(measured 1,872 rows / ~13ms in the real production database, via a
read-only backup) using aware-`datetime` ordering — zero floating-point
loss at any sub-second granularity, correct across mixed UTC offsets by
construction (not raw TEXT comparison, still offset-unsafe). Implemented
as a shared `_latest_snapshot_at_or_before(cutoff, *, inclusive)` helper
used by both `get_latest_snapshot_as_of` and `get_latest_snapshot_before`
— ID-5G's INCLUSIVE/STRICT semantic distinction is completely preserved,
only the comparison's precision changed. `get_latest_snapshot_before` was
found to share the identical precision bug (adjacent fix, not a
scope-broadening rewrite) and was fixed via the same helper.
`get_latest_snapshot()`/`list_snapshots_recent()`'s own theoretical
mixed-offset raw-ordering risk was reported honestly, not fixed — neither
has a caller demonstrably needing chronological-latest correctness (a
write-integrity equality check and live-only dashboard reads,
respectively). Non-vacuously proven at both levels: reverting the fix
made a same-second-selection test wrongly pick a non-maximal value, and
made a real pipeline run leak an extreme future `india_vix` value (with
insertion order deliberately reversed, since SQLite's own tie-break for
equal-after-truncation rows was empirically found to favor whichever row
was inserted first — a caution worth keeping in mind for any future
truncation-adjacent test). 8 new tests (20 total across ID-5G + ID-5G.1).
Full suite: 2,935 passed, 1 pre-existing skip. Zero new mypy failures.
Candle (ID-5E), quote (ID-5F), and market-snapshot (ID-5G + ID-5G.1)
market-time retrieval are now all closed with full sub-second, offset-safe
precision. ID-5B remains untouched and separately gated on 2026-08-31.

## Explosive Move Radar Research Track (accepted 2026-08-21)

**Source:** Owner assignment dated 2026-08-21

**Roadmap:** `docs/design/ATHENA-EXPLOSIVE-MOVE-RADAR-ROADMAP.md`

**Architecture gate:** `docs/adr/ADR-012-explosive-move-radar-boundary.md`

This track proposes an isolated, research-first ATHENA lane for estimating the
historically calibrated probability of exceptional intraday moves. It is not a
trade signal, does not alter canonical ATHENA scoring, confidence, risk,
Decision, or TradePlan contracts, and never places orders. DarvaX remains an
independent advisory lane.

ADR-012 is accepted; EM-0, EM-1a, EM-1r1, EM-1r2, EM-1r3, EM-1r4, and
EM-1r5 are all owner-approved. EM-1a's own zero-checkpoint audit is
superseded by EM-1r5's real re-audit: **all 9 candidate checkpoints are
now accepted** (`config/explosive_move.json`), on the strength of the
corrected real EM-1r3 production capture. Acceptance means research-ready
evidence, explicitly not predictive value, calibration, or production-
scanner fitness — see the EM-1r5 note below and
`artifacts/research/em1r5/reaudit_result.json` for the measured evidence.
EM-1b's deterministic production label dataset has been generated and the
owner-approved chronological TRAIN/VALIDATION/CALIBRATION/FINAL_TEST
partitions (2026-08-26) assigned — see `config/explosive_move.json`'s
`_meta.partition_contract` and `artifacts/research/em1b/dataset_index.json`.
Awaiting Milestone Review Summary approval before EM-1c starts. AUX-8 is
approved on the independent DarvaX/Symbol-360 track; accepting this
independent research track does not silently advance either track.

| Milestone | Objective | Status |
|---|---|---|
| EM-0 | Review and accept the isolated EMR architecture boundary | ✅ Approved 2026-08-21 |
| EM-1a | Audit historical coverage, survivorship, corporate actions, and event-label feasibility | ✅ Approved 2026-08-21 — zero checkpoints accepted |
| EM-1r1 | Freeze remediation architecture, ordering, provenance, and acceptance gates | ✅ Approved 2026-08-21 |
| EM-1r2 | Acquire authoritative corporate actions and persist bounded provenance | ✅ Approved 2026-08-21 |
| EM-1r3 | Reconstruct canonical duplicate-free complete intraday sessions | ✅ Approved 2026-08-21 |
| EM-1r4 | Apply the frozen survivor-cohort contract to research admission and enforce quote-timestamp hygiene | ✅ Approved 2026-08-22; 2,216 tests pass |
| EM-1r5 | Re-audit coverage and approve a non-empty checkpoint set | ✅ Approved 2026-08-26 — all 9 candidate checkpoints accepted (research-ready, not predictive-value-approved) |
| EM-1b | Build the deterministic point-in-time research dataset and labels | ✅ Approved 2026-08-27 — dataset generated, chronological partitions assigned |
| EM-1c prerequisite | Acquire and replay real historical NIFTY 50/INDIA VIX regime evidence (owner-mandated before EM-1c can use regime) | ✅ Approved 2026-08-27 — 743/743 sessions classified, 0 UNKNOWN; three real calendar defects found and fixed |
| EM-1c | Publish unconditional base rates (TRAIN-only) and freeze minimum cohort support | ✅ Approved 2026-08-27 — base rates published across all required dimensions; minimum-support policy frozen (n≥1,000, k≥10) |
| EM-2 | Implement cutoff-safe feature families and feasibility gates | ✅ Approved 2026-08-27 — 28-field evidence contract (em2-evidence-v1) generated for TRAIN (206,351 symbol-day rows, 1,857,159 checkpoint snapshots) |
| EM-3 v1 | Publish historical conditional analysis and defensible feature selection | ✅ Approved 2026-08-27 — univariate, checkpoint-level TRAIN analysis: 185,004 cells, 14,727 EXPLORATORY_CANDIDATE |
| EM-4A | Deterministic evidence score (frozen vote rules over EM-3's register) | ✅ Approved 2026-08-27 |
| EM-4B | Fit 18 pooled logistic baselines (TRAIN-only, chronological CV) | ✅ Approved 2026-08-27 — all 18 (family×threshold) models converged, deterministic replay verified; C=0.01 selected for 13/18, 0.1 for 4/18, 1.0 for 1/18 |
| EM-4C | Open real VALIDATION outcomes; compare deterministic vs. logistic vs. base rate | ✅ Approved 2026-08-28 (GO) — logistic beats deterministic on PR-AUC in 18/18 real (family×threshold) combinations; logistic Precision@10/Lift@10 real and consistent across all 9 checkpoints and all 3 regime dimensions for the TOUCH_10 flagship |
| EM-4D | Platt-scaling calibration of all 18 frozen logistic models (CALIBRATION only) | ✅ Approved 2026-08-28 (GO) — all 162 (family×threshold×checkpoint) cells calibrated (135 checkpoint-specific, 27 pooled fallback), 0 insufficient-support, 0 unstable-fit |
| EM-4E | Sealed FINAL_TEST evaluation (run once) | ✅ Owner-approved / GO 2026-08-28 — real, one-shot FINAL_TEST read complete (702,702 checkpoint rows, 157 sessions); calibrated logistic beats deterministic on PR-AUC in 18/18 real combinations, replicating EM-4C's VALIDATION finding on a third, independent, never-before-touched partition; checkpoint/regime stability and flagship excursion both confirmed consistent with VALIDATION. FINAL_TEST remains sealed |
| EM-5 | Implement the replayable bulk-input live scanner without UI | ✅ **OWNER APPROVED / CLOSED — 2026-09-01** — contract `ACCEPTED` (Owner/Chief Architect, 2026-08-28). Regime wiring RESOLVED; REL_VOLUME_C historical support REPAIRED; Track B.1 OWNER-ACCEPTED with corrected Tuesday 2026-09-01 classification `NO_OFF_GRID_PROVISIONAL_OBSERVED`, clearing `CANARY_BLOCKED_LIVE_M5_SEMANTICS` for the frozen Tuesday canary. Final validation checkpoint ran the unchanged Section 14 full nine-checkpoint production canary against `athena_core` / 2026-08-28 via `run_em5_production_canary()`: PASS, 518/518 mature instruments, 9,324/9,324 all-required-fields-known at every checkpoint (100.0000%), 99% floor PASS, relative baseline PASS, frozen artifact hashes PASS, checkpoint-boundary regression PASS, freshness PASS, hard eligibility PASS, zero provider/network calls PASS, replay determinism PASS. Full suite passed (2,956 passed, 1 skipped); Ruff clean on EM-5/Track B.1 modified Python files; `git diff --check` clean; Track B/ID-5B artifact hashes preserved. EM-6/7/8 and ID-6 are not started |
| EM-6 | Add the EMR research UI only after scanner approval | Planned |
| EM-7 | Run isolated shadow validation and OFF-vs-shadow performance comparison | Planned |
| EM-8 | Decide research-only, continued shadow, retirement, or a new integration ADR | Planned |

**Note on the EM-1r4 title (2026-08-22):** earlier drafts of this row read
"Freeze point-in-time cohort," which reads as if EM-1r4 acquires genuine
point-in-time historical NSE membership. It does not, and the handoff doc
and remediation plan are both explicit that doing so is an explicit
non-goal (that would require a new external data-source decision). The
title above is corrected to say what the milestone actually does: apply
the *already-frozen* EM-1r2 survivor-cohort contract to admission
decisions, honestly labelled as survivor-cohort research rather than
point-in-time history.

**EM-1r4 was owner-approved 2026-08-22.** New pure
domain module `src/athena/explosive_move/cohort_admission.py`
(`assess_symbol_day_cohort_admission`, `assess_quote_timestamp_hygiene`,
`CohortAdmissionManifest`) plus a Data-layer orchestration service
(`src/athena/data/cohort_admission_ingestion.py`, `run()`/`replay()`,
mirroring EM-1r3's own separation of calendar resolution from pure
admission logic). No provider, no network call, no schema change — EM-1r4
introduces no new external evidence, only classification over what's
already persisted. 34 new tests (28 pure-contract, 6 real-repository
integration), two proven non-vacuous by reintroducing the exact bug each
catches, plus a third non-vacuous regression test for a genuine bug found
during real-data verification (the ingestion service crashed on any quote
timestamp landing in a year the calendar engine has no data for — e.g. the
real 1970 epoch-default rows — instead of excluding it; fixed by treating
"no calendar authority for this date" as fail-closed exclusion, not a
crash). Full suite **2,216 passing** (2,181 → 2,215 initial → 2,216 after
the calendar-coverage fix).

**Real production-scale evidence** (run against a scratch copy of the real
database, never the original — the service only reads canonical tables):
518 survivor-cohort instruments; 81,326 symbol-days assessed over
2026-01-01..2026-08-21 (the only interval the real calendar config
currently covers — a genuine, reported limitation, not a workaround), all
81,326 admitted (0 listing/delisting exclusions, since no instrument in
this ledger has a populated `listed_date`/`delisted_date` yet — the
contract and its test coverage exist for when such evidence becomes
available); 196,461 quotes assessed for those same cohort instruments, 511
rejected as Unix-epoch defaults, 14,103 rejected as outside session
bounds, 0 outside study bounds, for a combined 7.4% quote rejection rate.
Deterministic replay reproduced an identical `replay_id` from the
manifest's own frozen inputs alone (never re-reading the live, mutable
canonical tables). See `IMPLEMENTATION_SUMMARY.md`'s EM-1r4 entry for full
detail.

**EM-1r3 production capture (in progress, 2026-08-22).** Before starting
EM-1r5, discovered EM-1r3 had only ever been fixture-tested, never run at
production scale — owner authorized a real, resumable, rate-limited
capture across the full 518-instrument survivor cohort and the frozen
2023-08-11..2026-08-21 study window. Built (all tested, EM-1r3's own frozen
contract in `intraday_reconstruction.py`/`intraday_reconstruction_ingestion.py`
unmodified except the one calendar-correctness change below):
`src/athena/data/retrying_provider.py` (bounded retry/backoff for transient
network/5xx provider failures only — the transport already retries 429s),
`src/athena/data/intraday_production_capture.py` (checkpointed, resumable
per-instrument batching over EM-1r3's own `capture()`, plus a neutral
`RecentHistoryTruncationObservation` evidence field — a real, reproducible
pattern found diagnosing this work: recent-session 5-minute Kite data is
truncated to 72 of 75 slots inside roughly the last ~2-3 weeks, confirmed
not an ATHENA request-construction defect; framed as an unverified
hypothesis, never asserted as confirmed provider behavior, per owner
instruction). 48 new tests, all passing; two failure-classification helpers
proven non-vacuous.

**Calendar-contract correction (owner-approved 2026-08-22).** Launching the
sweep against the full study window surfaced that `config/calendar/holidays.json`
only had 2026 data — `CalendarEngine` fails loudly for any other year, which
would have crashed EM-1r3's session enumeration at 2023-08-11. Researched and
populated authoritative NSE Capital Market Segment (CMTR) circulars for
2023–2025 (holidays, both 2024 election-holiday addenda, and Muhurat dates —
see `holidays.json`'s `_meta.sources` for full per-year circular provenance).
That research also surfaced a real `CalendarEngine` bug: every `special_sessions`
entry was hardcoded to `SessionType.MUHURAT` regardless of its configured
`type`, so a genuine full-shaped Saturday session (2025-02-01, NSE/CMTR/65729,
the Union Budget live session) would have been misclassified and silently
excluded from EM-1r3 capture. Fixed narrowly: `CalendarEngine` now reads
`SpecialSession.type` from configuration (restricted to `MUHURAT`/`SPECIAL`,
fails loudly otherwise); `_regular_sessions()` now treats `SPECIAL` exactly
like `NORMAL` for capture. A second finding — confirmed-live but
split/multi-window DR-drill sessions (2024-01-20, 2024-03-02) — cannot be
represented by the single open/close-window model; per explicit owner
instruction, these are **not** forced into the model. A new
`SessionType.KNOWN_UNSUPPORTED_SPECIAL_SESSION` and a new
`known_unsupported_special_sessions` config list make this an explicit,
queryable exclusion instead of a silent `WEEKEND` misclassification; EM-1r3
still excludes them from capture (no schema/contract change to
`intraday_reconstruction.py`). 8 new tests (calendar + EM-1r3 ingestion),
all three new behaviors proven non-vacuous by reintroducing the exact bug
each guards against. Full suite **2,254 passing**, Ruff clean.

**EM-1r3 production sweep INVALIDATED (2026-08-24).** The real sweep
launched under the calendar fix above ran to completion (~49 hours,
518/518 instruments, two Kite token-expiry recoveries) — but a
post-completion audit found 0 of 385,910 sessions admitted. Root cause: a
confirmed, live-verified defect in `KiteProvider._historical()` (Kite's
`to` boundary is exclusive of a candle whose open time equals it exactly;
EM-1r3's own all-or-nothing admission rule then correctly excluded nearly
every session). Not a data-availability problem — the underlying market
data was present the whole time. Fixed (`kite_provider.py`, one-interval
`to` widening for intraday timeframes, existing per-row filter unchanged
so nothing can leak beyond the caller's requested range), tested (11 new
tests, non-vacuous), and re-verified live across multiple instruments and
dates before spending further Kite quota. The invalidated run's 5.8GB of
evidence was preserved (not deleted) at
`artifacts/research/em1r3-INVALIDATED-2026-08-24-provider-boundary-defect/`
with a full written notice. See `IMPLEMENTATION_SUMMARY.md`'s top entry
for complete detail.

**Permanent process rule adopted (CLAUDE.md, 2026-08-24):** every
expensive external-data-provider run must now pass a real-provider canary
with an explicit admission/quality threshold, with automatic fail-fast if
it misses, before scaling out — codified in
`src/athena/data/em1r3_production_canary.py` and wired into the capture
CLI so it cannot be silently skipped.

**EM-1r3 corrected production capture COMPLETE (2026-08-26).** Ran
2026-08-24 15:27 UTC to 2026-08-26 14:05 UTC (46.63 hours true capture
time, three token-expiry cycles all auto-recovered by the supervisor).
**92.81% of all 385,910 requested sessions admitted** (358,177) — a
complete reversal from the invalidated run's 0%. 104/104 manifests
deterministically replay-verified, zero failures. Full test suite 2,270
passing. Two new findings from running at true scale, both reported
honestly: a single-day, 100%-uniform, cause-unverified anomaly
(2024-01-22, 518/518 zero-candle sessions, immaterial at 0.13% of
population) and the already-disclosed survivor-cohort late-listing
limitation now empirically visible (137 instruments, mostly explained by
not-yet-listed status at study_start). See `IMPLEMENTATION_SUMMARY.md`'s
top entry for the complete Review Summary.

**EM-1r5 APPROVED (2026-08-26).** Re-ran EM-1a's coverage measurement
against the real, corrected EM-1r2/EM-1r3/EM-1r4 evidence
(`src/athena/data/em1r5_checkpoint_reaudit.py`). All 9 candidate
checkpoints show identical, substantial admitted-symbol-day support —
356,225 for TOUCH/CLOSE, 358,177 for OPEN_TO_HIGH — since the relevant
gates (admitted intraday session, cohort membership, corporate-action
boundary validity) are all session-level facts under today's evidence,
not checkpoint-time-level facts. Owner approved promoting all 9 to
`accepted_ist`, explicitly as research-ready evidence only — not
predictive value, calibration, or scanner fitness; that differentiation
is deferred to EM-1c onward.

New reusable contract, owner-designed: corporate-action contamination is
**calculation-window-dependent, not proximity-window-dependent**
(`src/athena/explosive_move/corporate_action_boundary.py`) — a rejected
alternative fixed ex-date+N-session window was measured and shown to
over-exclude by 5,970-7,971 symbol-days versus the adopted boundary rule.
Real measured impact: 2,001 TOUCH/CLOSE symbol-days flagged (1,952 as the
sole exclusion reason, ~0.51% of population); OPEN_TO_HIGH mathematically
immune (0 flagged), confirmed empirically. Six real DEMERGER actions
flagged as an explicit, unresolved `IDENTITY_CHANGE_RISK` provenance
limitation, carried forward for future feature/model work to check
against, not resolved here. Full evidence:
`artifacts/research/em1r5/reaudit_result.json`. Full suite 2,284 passing.

**EM-1b Chronological Partition Proposal APPROVED (2026-08-26).**
Owner/Chief-Architect-approved exact TRAIN/VALIDATION/CALIBRATION/
FINAL_TEST cutoff dates, backed by real measured eligible-observation and
positive-event distributions across the full frozen study window
(`artifacts/research/em1b/partition_measurement.json`, 743 real trading
sessions, 355,724-357,659 eligible symbol-day observations depending on
family). TRAIN 2023-08-14→2025-05-31 (440 sessions, 59.2%), VALIDATION
2025-06-01→2025-09-30 (85, 11.4%), CALIBRATION 2025-10-01→2025-12-31 (61,
8.2%), FINAL_TEST 2026-01-01→2026-08-21 (157, 21.1%) — sealed per the
approval's FINAL_TEST-sealing rule. Frozen contract:
`src/athena/explosive_move/partitions.py` and
`config/explosive_move.json`'s `_meta.partition_contract`.

**EM-1b production label dataset GENERATED and APPROVED (2026-08-27).**
`src/athena/data/em1b_label_dataset_generation.py` produced the full
deterministic symbol-day and checkpoint label dataset
(`artifacts/research/em1b/{labels,manifests,dataset_index.json}`),
partition-assigned per the approved cutoffs above. A real determinism bug
was found and fixed during this milestone (gzip's default wall-clock
mtime header made byte-identical content hash differently across runs);
fixed with a pinned `mtime=0` writer and locked down with a non-vacuous
regression test. Owner-approved the same day. See
`IMPLEMENTATION_SUMMARY.md`'s EM-1b entry for the full Milestone Review
Summary.

**EM-1c prerequisite: historical regime evidence (2026-08-27), pending
review.** Before EM-1c can report base rates by regime, the canonical
`RegimeEngine` needed real historical NIFTY 50/INDIA VIX D1 history it
never had. Acquired 2023-05-01→2026-08-21 via the corrected KiteProvider
path (`src/athena/data/em1c_regime_evidence_acquisition.py`), found and
fixed **three real calendar defects** in the process — confirmed via
NSE's own circulars, not guessed: the 2023 Bakri Id holiday was later
revised from June 28 to June 29 (NCL/CMPT/57291) and the calendar still
had the superseded date; two undocumented full/special sessions
(2024-05-18 DR-drill, 2026-02-01 Union Budget Sunday session) were
missing entirely. Resolved 14 real INDIA VIX value discrepancies via an
explicit source-authority policy (no canonical DB overwrite). Then
chronologically replayed the completely unmodified `RegimeEngine` across
all 743 real EMR study sessions
(`src/athena/explosive_move/regime_replay.py` +
`src/athena/data/em1c_regime_historical_reconstruction.py`) with an
explicit, 9-test-proven point-in-time-safe rule (session T's regime uses
only D1 history strictly before T for trend/volatility; T's own real
open, never its close/high/low, for gap) — contract audit found ATHENA's
own live system is naturally T-1-cutoff-safe by construction (today's D1
candle doesn't exist until the 15:45 IST CLOSING cycle), so this
replicates real production behavior, not a new invented rule. **Result:
743/743 sessions (100%) got a complete regime classification, zero
UNKNOWN.** See `IMPLEMENTATION_SUMMARY.md`'s top entry for the full
review.

**EM-1c APPROVED (2026-08-27).** Computed real,
TRAIN-only base rates directly from EM-1b's own approved dataset
(3.7M symbol-day rows, 33.4M checkpoint rows) across every required
dimension (family, threshold, checkpoint, TRAIN-period year, sector,
canonical regime) — every rate with a Wilson 95% CI
(`src/athena/explosive_move/wilson_interval.py`). Froze the minimum-
support policy (**n≥1,000, k≥10**) directly from the real support
distribution: family/threshold/year/checkpoint/regime breakdowns pass
almost universally, while sector breakdowns correctly fail 25.1% of the
time (95/378 cells), concentrated exactly at small sectors × rare
thresholds. Headline TOUCH_10 rate: 1.08% (n=205,303, k=2,226). Real,
well-supported descriptive findings flagged as EM-2/EM-3 hypotheses (not
claimed as feature lift here): GAP_UP sessions show ~2.7x the TOUCH_10
rate of GAP_DOWN sessions; HIGH_VOLATILITY sessions show ~2x the rate of
LOW_VOLATILITY sessions.

**EM-2 APPROVED (2026-08-27).** Implemented the owner-approved,
contract-corrected `em2-evidence-v1` manifest — exactly 28 fields (15
SESSION_INVARIANT: 13 PRIOR_HISTORY + 2 SESSION_OPEN_CONTEXT; 13
CHECKPOINT_DYNAMIC), each classified EVIDENCE_ONLY or CANDIDATE_FEATURE,
every canonical indicator (SMA/EMA/RSI/ATR/MACD/ADX/VWAP) reused
completely unmodified from `athena.indicators.calculations`. Generated
the real TRAIN evidence dataset: 206,351 symbol-day rows, 1,857,159
checkpoint snapshots (518 instruments). UNKNOWN rates are real and
honest — 0% for regime-conditioned fields (thanks to EM-1c's own extra
warm-up acquisition), climbing from ~1% (GAP_PCT) to ~12% (SMA50_REL)
purely from the accepted, un-remediated pre-TRAIN warm-up shortfall.

**EM-3 v1 conditional analysis PUBLISHED (2026-08-27), pending review.**
Joined EM-2's 22 CANDIDATE_FEATURE fields with EM-1b's checkpoint-level
labels and EM-1c's checkpoint-specific baselines, TRAIN only, univariate
and checkpoint-level per the owner's approved v1 scope
(`src/athena/explosive_move/conditional_analysis.py` +
`src/athena/data/em3_conditional_analysis.py`). Real result: 1,857,159
joined rows → 185,004 aggregation cells → **14,727 EXPLORATORY_CANDIDATE**
(never `VALIDATED_SIGNAL`, a forbidden term), 2,121 `INSUFFICIENT_SUPPORT`,
2,124 `MISSINGNESS_DIAGNOSTIC`, all stamped `TRAIN-DISCOVERED / UNVALIDATED`.
Strongest real finding: REL_VOLUME_C's top quintile at 09:20 shows 2.75x
lift over TOUCH_10's checkpoint baseline (n=38,706, k=1,031), rising to
3.58x by 14:00 even as its raw rate falls with natural ALREADY_OCCURRED
attrition — raw rate and relative lift move in *opposite* directions
across the session. Shape distribution across 3,078 groups: 56.1%
U-shaped, 26.2% monotonic increasing — real, descriptive, not acted on
here. Interactions, rule mining, and any model work are explicitly
deferred, recorded in every manifest, not silently dropped. See
`IMPLEMENTATION_SUMMARY.md`'s top entry for the full review.

**Current handoff:** Read `docs/ATHENA-EMR-HANDOFF.md`. EM-3 v1's
conditional analysis is published and self-validated, awaiting
Owner/Chief Architect Milestone Review Summary approval. EM-4
(expansion probability model) has not started.

## Advisory UX Priority Track (selected 2026-08-19)

Owner-approved delivery order selected from
[`docs/design/ATHENA-DARVAX-UX-ROADMAP.md`](design/ATHENA-DARVAX-UX-ROADMAP.md).
The remaining roadmap ideas are still an unscheduled menu. AUX-1 was split
before implementation because ATHENA's intraday freshness and DarvaX's daily
sweep freshness require separate authoritative contracts.

| Order | Milestone | Scope | Status |
|---:|---|---|---|
| 1 | **AUX-1a** | Server-authoritative ATHENA freshness DTO and persistent Decisions/Market header indicator | ✅ Approved 2026-08-19 |
| 1b | **AUX-1b** | Calendar-aware DarvaX sweep/data freshness using the shared semantics | ✅ Approved 2026-08-19 |
| 2 | **AUX-2** | Visible last successful ATHENA cycle and overdue warning outside Live Operations | ✅ Approved 2026-08-20 |
| 3 | **AUX-3** | Confidence band visible in the Decisions list | ✅ Approved 2026-08-20; 2,028 tests pass |
| 4 | **DX-12b** | DarvaX 50/100 EMA trend badge on Advisor cards and Levels view | ✅ Approved 2026-08-20; 2,041 tests pass |
| 5 | **AUX-4a** | ATHENA daily near-miss digest (score-margin, in DailyBriefingBuilder) | ✅ Approved 2026-08-20; 2,055 tests pass |
| 5b | **AUX-4b** | DarvaX's own near-miss digest, written once per completed sweep | ✅ Approved 2026-08-20; 2,069 tests pass |
| 6 | **AUX-5** | ATHENA “My track record” rollup over existing journal/outcome data | ✅ Approved 2026-08-20; 2,075 tests pass |
| 7 | **AUX-4c** | Surface near-miss digests in the dashboard UI (ATHENA + DarvaX) — both currently file-only, per AUX-4a/4b's own design | ✅ Approved 2026-08-20; 2,086 tests pass |
| 8 | **AUX-6** | "See the other view" cross-link — quiet affordance linking a symbol's ATHENA Decision Brief and its DarvaX read, and vice versa | ✅ Approved 2026-08-21; 2,105 tests pass |
| 9 | **AUX-7** | "Symbol 360" page — ATHENA Decision, DarvaX screen result, saved-symbol status, and journal history for one instrument, side by side | ✅ Approved 2026-08-21; 2,165 tests pass |
| 10 | **AUX-8** | "Scan & Validate" on Symbol 360 — on-demand ATHENA validation + DarvaX scan for one symbol, run concurrently | ✅ Approved 2026-08-21; 2,181 tests pass |

DX-12b was owner-approved 2026-08-20 after live visual verification on the
owner's own real system. AUX-4 was split into AUX-4a/AUX-4b before
implementing, the same way AUX-1 was split, because the owner chose to cover
both surfaces and DarvaX architecturally cannot be pulled into ATHENA's
notification module (ADR-010's one-way isolation seam).

**AUX-4a and AUX-4b were both owner-approved 2026-08-20**, each independently
confirmed on the owner's own real, live system (129 real near-misses in a
real `athena brief --dry-run` run; 35 real near-misses in a real DarvaX
sweep, with the math spot-checked by hand against the digest's own numbers).

**AUX-4c was owner-approved 2026-08-20**, after a same-day copy refinement
pass (owner verified live, then asked for the term "near miss" itself to be
self-explanatory — both panels gained a plain-language explainer; see
IMPLEMENTATION_SUMMARY.md's AUX-4c entry for the "Composite score" naming
collision this caught and fixed along the way). Both AUX-4a and AUX-4b
were file-only by design, matching the roadmap item's own "folded into the
existing morning briefing" wording — neither surfaced in the ATHENA
dashboard or DarvaX's own UI. Design resolved to reading each digest's
already-persisted file directly (mirroring `OpsService.list_backups`'
glob-directory-plus-defensive-JSON-parse convention) rather than adding new
persistence — a missing/corrupt file degrades to an honest empty state
(`as_of=None` distinct from "ran and found none"), never a fabricated
result. ATHENA: new `GET /api/v1/decisions/near-misses` reads the most
recently modified `brief-*.json` under the configured file-notifier output
dir; surfaced as a new "Near Misses" card on the Overview tab. DarvaX: new
`GET /darvax/api/screen/near-misses` reads the most recently written
`near-miss-*.json` under the configured digest dir; surfaced as a new "Near
misses" zone in the Advisor view, independent of the live sweep state by
design (it can go stale between sweeps, same as the digest itself). Verified
live against an isolated scratch server for the DarvaX side; the ATHENA
side's verification incidentally read the owner's real, current
`artifacts/briefings/brief-2026-08-20.json` (a pre-existing characteristic
of `get_decisions_service`'s dependency wiring, which resolves `config_dir`
to the real repo root regardless of `ATHENA_CONFIG_DIR` — read-only, no
write, but flagged as a risk below since it affects verification
methodology, not just this milestone).

**AUX-5 was owner-approved 2026-08-20.** Scoped ATHENA-only per the
roadmap doc's own "Surface: ATHENA" tag — "DarvaX's own realized-performance
view" is a separate, unscheduled roadmap idea, not part of this milestone.
Real-data check before design: `decision_journal`, `trade_outcomes`, and
`darvax_positions` are all at zero rows on the owner's live system, so this
was verified against fixtures, not real history — same non-vacuous-guard
verification discipline as AUX-4a/4b, applied at the unit level since there
was no live sample to check against. New read-only `GET
/api/v1/decisions/track-record` reuses the exact win-rate/avg-return/
avg-holding arithmetic already established for decision analogs (M-X1,
`_outcome_return_and_holding`) rather than inventing new math — "avg return
%" over closed outcomes, not the roadmap wording's "R-multiple", since that's
what the codebase already computes and persists. Surfaced as a new 3-card row
on the Overview tab (Win Rate / Avg Return per Trade / Plan Adherence) with
an explicit empty state ("No closed trades yet" / "No journal entries yet")
rather than a fabricated zero.

**AUX-4a** (ATHENA) reframed from the
roadmap's "symbols close to their buy trigger" wording after finding ATHENA
persists no entry-price level short of a TRADE decision
(`Decision.trade_plan` is `None` otherwise) — the honest, already-persisted
near-miss signal is a WATCH decision's composite-score gap to the trade
threshold, reusing the exact arithmetic already shipped for the decision
counterfactual endpoint (M-X2). Verified live against the owner's real
database (read-only; row counts confirmed unchanged): 112 real near-misses
found and rendered correctly.

**AUX-4b** (DarvaX). The owner resolved the trigger question directly: the digest fires once per completed sweep rather
than on any schedule, which inherits DX-4a's "never scheduled" design by
construction. Reuses `distance_to_breakout_pct` (DX-3, already persisted) --
the same field the Levels view's "Approaching their level" zone reads -- with
the same trigger-then-ceiling fallback `distance_to_breakout()` itself uses.
A file-only writer, self-contained in `athena.darvax` per this satellite's
own established convention of duplicating small logic rather than importing
`athena.notifications`. Verified live against an isolated scratch sweep
(never the owner's real `db/darvax.db`): 35 real near-misses found and
correctly worded ("clears" vs "buy above" depending on which level was
used). One real defect caught by that live verification and fixed before
review: the first version required `trigger_price` specifically and silently
discarded all 37 real candidates a fresh sweep actually had, since DX-3 sets
`trigger_price` only alongside a stop and essentially no WATCH row carries
one.

**AUX-6 and AUX-7 are newly registered, from the "Unify the two advisory
lanes" roadmap category.** The owner-selected priority track (AUX-1a
through AUX-4c) closed fully approved 2026-08-20; these are the owner's
next pick from the still-unscheduled menu. The roadmap doc lists these as
two separate items of very different size — "See the other view" cross-link
(Medium effort) and the full "Symbol 360" page (Big bet) — and the owner
confirmed wanting both. Split before implementation the same way AUX-1 and
AUX-4 were: AUX-6 (the smaller cross-link) starts Design first; AUX-7
(Symbol 360) is queued behind it and will very likely need its own
sub-milestone split once its Design step runs, given its "Big bet" sizing.

**AUX-6 was owner-approved 2026-08-21**, confirmed working on the owner's
own real system after five owner-caught fix passes the same day (see
IMPLEMENTATION_SUMMARY.md's AUX-6 entry for the full account of each one —
worth reading before touching either dashboard's cross-lane code again).

**AUX-6, as shipped, surfaced a real
architectural boundary mid-implementation.** ADR-010 Amendment 1's existing,
test-enforced rule ("ATHENA's own dashboard assets may never reference
DarvaX by name anywhere but one script tag") turned out to forbid the
ATHENA -> DarvaX half of this feature exactly as first built (ATHENA's
Decision Brief calling a DarvaX endpoint directly) — caught immediately by
the full test suite (`test_dx4_surface.py`, `test_dx4b_tab.py`), not
discovered late. Rather than weaken that boundary, the ATHENA -> DarvaX
link is instead injected entirely from DarvaX's own `tab.js` — the one file
already responsible for DOM-injecting things into ATHENA's page (DX-4b) —
which watches `#decision-brief-title` for a real instrument and adds a
quiet link only when DarvaX has a signal for it. No ADR amendment needed;
this fits inside the existing Amendment 1 pattern rather than extending it.
The DarvaX -> ATHENA half needed no such workaround (DarvaX may read ATHENA
by design) and lives directly in `darvax.js`, bulk-fetching
`GET /api/v1/decisions/latest` once per page load. Both links navigate in
the **same tab** (see the fix below for why) rather than touching the
DarvaX nav tab's iframe at all. Verified live end-to-end on an isolated
scratch server in both directions, including the
`?decision=`/`?symbol=&mode=table` deep-link plumbing each side needed —
though see below, that scratch verification had a real gap.

**Three real bugs caught by the owner's own live screenshots across three
fix passes the same day — the first two attempts each insufficient in a
different way.** Both links originally opened in a new tab
(`target="_blank"` + `rel="noopener"`) under a mistaken belief that this
was needed to avoid the DarvaX nav tab's iframe going stale; in fact
neither link ever touches that iframe, so the new-tab behavior solved a
problem that didn't exist while creating a real one — every click landed
on a login screen instead of the target page. **Attempt 1**: dropped
`noopener`, theorizing the new tab would then inherit `sessionStorage`
(where the ATHENA token lives) from its opener. Owner re-tested, identical
failure. **Attempt 2**: dropped `target` entirely, same-tab navigation —
this genuinely fixed the auth failure (same browsing context, nothing to
inherit), but broke a *different* case on the very next owner screenshot:
viewed through ATHENA's own embedded "DarvaX" nav tab (an iframe), an
untargeted link only navigates that iframe, so clicking the DarvaX-side
"ATHENA ↗" chip opened a second, nested ATHENA dashboard inside the DarvaX
pane instead of the real one. **Attempt 3, the actual fix**:
`target="_top"` on the DarvaX -> ATHENA link only — always navigates the
outermost window of the current tab (still no new browsing context, so
auth is untouched), and is a harmless no-op when not embedded. The
ATHENA -> DarvaX link never needed this, since `tab.js` only ever runs in
ATHENA's own top-level page and is never itself nested. Separately, the
injected ATHENA-side link had also rendered as a full-width banner rather
than a small chip (column-flexbox `align-self` default) — fixed with an
explicit `align-self`. **Testing-methodology gap surfaced by this**: every
scratch-server verification here used the `ATHENA_SINGLE_USER=true` auth
bypass for convenience, which disables the auth check entirely — neither
of the first two live-verification passes actually exercised real
authentication, which is exactly why attempt 1 looked correct in scratch
testing.

**A fourth bug, same day: the ATHENA -> DarvaX link's destination, not
just its target.** Even after `target="_top"` fixed the nesting, the link
still pointed straight at DarvaX's standalone `/darvax/...` page — clicking
it replaced the whole ATHENA dashboard, sidebar and all, exactly the
"sidebar of tabs is missing" the owner caught from a real screenshot. Fix:
the link now points at `tab.js`'s own embedded-tab route
(`/dashboard/darvax?symbol=&mode=`) instead, and `build()` was extended to
read those same params back out of the URL and forward them into the
iframe's `src`, so the embedded view opens pre-scoped rather than
unfiltered. Verified correct by direct inspection of the constructed
`iframe.src`. **One thing this session's scratch-testing tool could not
conclusively confirm** — flagged as possibly a tooling artifact — **turned
out to be a real, fifth bug**, confirmed once the owner re-tested on their
own system: the sidebar stayed correctly, but the content pane showed
Overview, not DarvaX. Root-caused by temporarily instrumenting a live page
(patched `classList.remove`/`className` to log a stack trace on every
mutation) rather than guessing further: `tab.js`'s own governing comment
claiming ATHENA's `navItems`/`tabPanes` are a stale snapshot "invisible" to
this tab was wrong for this exact timing. ATHENA's own bootstrap captures
those NodeLists (and runs `switchTab("overview")`, since "darvax" isn't
one of its own tab ids) only *after* an async auth-status fetch resolves —
which happens after this file's synchronous `build()`/`activate(false)`
has already run and injected the pane, so by the time `switchTab` captures
its NodeLists, this pane already exists and gets included — and promptly
deactivated. No fixed delay can reliably win that race, so the fix adds a
`MutationObserver` that watches for exactly this clobbering and reasserts
activation once, then disconnects (both on success and after a 5-second
safety timeout), so it never fights a real, later, deliberate tab switch.
Re-verified live across three fresh page loads and a +800ms check: stayed
active every time; a genuine subsequent click to another tab still worked
normally.

See IMPLEMENTATION_SUMMARY.md's AUX-6 entry for full detail; regression
tests were rewritten/added across all five attempts to pin the final
design; full suite 2,105 passing.

**AUX-7 ("Symbol 360") is implemented and ready for owner review,
2026-08-21.** The Design step resolved the one open architectural question
AUX-6's handoff had deliberately left for a fresh pass — where does a page
needing *both* lanes' data live — by direct application of the same
ADR-010 Amendment 1 asymmetry AUX-6 had just proven: ATHENA-owned assets
may never reference DarvaX, but DarvaX may read ATHENA freely. So Symbol
360 is a DarvaX-owned standalone page (`/darvax/symbol360`), not an ATHENA
dashboard tab. Research confirmed **zero new backend endpoints** were
needed — every value (ATHENA's latest decision, DarvaX's screen-result row
with a raw-signal fallback when no current sweep row exists, saved-symbol
status, and a per-instrument journal-history join) is served by an
endpoint AUX-5, AUX-6, or ATHENA core already exposed and already tested.
Two entry points, both reusing patterns AUX-6 already had to get right the
hard way: an unconditional "View Symbol 360 →" link injected into
ATHENA's Decision Brief from `tab.js` (same-tab navigation, since `tab.js`
never runs nested — no `target` needed), and a "360°" chip on DarvaX's own
Advisor/Levels/Table cards (`target="_top"`, same reasoning as `athenaChip`,
since those cards can be viewed standalone or embedded in ATHENA's DarvaX
nav-tab iframe). Thirteen tests in `tests/darvax/test_aux7_symbol360.py`
cover the route, the ADR-010 guard (pinned explicitly for this feature, not
just inherited from the suite-wide scan), every endpoint the page's JS
calls, and both entry points' link construction; three of the most
safety-critical (the ADR-010 guard, the `target="_top"` chip, and the
iframe-routing fix below) were verified non-vacuous by temporarily
reintroducing the exact bug each guards against. Full suite 2,158 passing.

**A sixth instance of AUX-6's bug 4, caught by the owner the same day.**
Both AUX-7 entry points originally linked straight at
`/darvax/symbol360?symbol=...` — the exact "direct link to the standalone
page instead of the embedded tab's `ROUTE`" mistake AUX-6's postmortem had
already documented in detail, made again despite that postmortem being
read while designing these same two links. The owner's screenshots showed
ATHENA's sidebar gone entirely on both "View Symbol 360 →" and the "360°"
chip. Fixed by routing both through `tab.js`'s `ROUTE` with a new
`?view=symbol360` param, extending `build()`'s existing param-forwarding to
point the embedded iframe at `/darvax/symbol360` instead of the main
screener when present — the same mechanism AUX-6 built for
`?symbol=`/`?mode=`, just widened by one branch. Two new tests execute
`tab.js` in Node against the DOM-stub harness and assert the iframe's
actual `src`, not a source grep, matching this test file's own standard;
proven non-vacuous the same way as every other guard here. Live re-verified
reproducing the owner's exact click path: sidebar stays intact, the
embedded iframe correctly loads Symbol 360, and the page's own
"← DarvaX" back-link (now `embedded=1`-aware, mirroring `darvax.js`'s
existing convention) swaps the iframe back to the main screener in place.
See `IMPLEMENTATION_SUMMARY.md`'s AUX-7 entry for full detail, and the
handoff doc for the generalized lesson (citing a postmortem while
designing is not the same as re-checking its checklist against new code).

**Owner-approved 2026-08-21**, immediately followed in the same session by
a smaller post-approval polish pass on DarvaX Read's ACTION field, caught
by the owner from a live screenshot of a real `ACTIONABLE` row: the raw
DAR-CARD code (`ENTER_ON_RETEST`) was shown verbatim instead of going
through DarvaX's own existing `ACTION_LABEL` humanization (an AUX-7
oversight, not a new gap); a first fix additionally bracketed the trigger
price next to the label, which the owner then flagged as confusing
duplication against the already-adjacent "Buy above" row and had reverted;
and the label itself ("Buy on dip") was renamed app-wide to "Buy on
retest" per the owner's explicit choice, with a hover tooltip on both
`darvax.js`'s `actionChip` and Symbol 360's own Action row reusing the
row's existing persisted `action_reason_plain` (never a new sentence) to
explain the concrete retest mechanic. A second, independent polish item in
the same pass fixed the ATHENA Decision card's "As of" line, which showed
a raw ISO timestamp instead of ATHENA's own established readable-time
convention. Six new tests, two proven non-vacuous; full suite 2,165
passing. Live re-verified on a fresh scratch server. See
`IMPLEMENTATION_SUMMARY.md`'s AUX-7 entry for the full account.

Live-verified end-to-end on an
isolated scratch server (own config, own database, real
`ATHENA_SINGLE_USER` bypass never touching the owner's real
`db/athena.db`/`db/darvax.db`): the search flow, the ATHENA Decision card,
the DarvaX Read card's no-current-sweep-row fallback (a real 404 against
`/darvax/api/signals/...`, handled gracefully), the saved-symbol toggle's
full DELETE→POST round trip, the journal history table, and both entry
points — including clicking the injected ATHENA-side link end-to-end into
a correctly pre-populated Symbol 360 page.

**AUX-8 ("Scan & Validate" on Symbol 360) is implemented and ready for
review, 2026-08-21** — the owner's follow-up ask right after approving
AUX-7: "one option where user will enter symbol and result should be both
athena validation and darvax validation after scanning the symbol
properly." AUX-7's "Look up" only ever reads whatever each engine has
already persisted; this adds a second, explicit "Scan & Validate" button
(design confirmed with the owner as a *separate* action, not folded into
"Look up") that actually re-runs both engines for the current symbol,
concurrently, each card updating independently as its engine finishes.
ATHENA's half reuses the exact candidate-upsert-then-validate pipeline
`09-market-intelligence.js`'s `validateSymbolsNow` already uses (a real,
scoped Kite ingest); DarvaX's half reuses the existing per-instrument
`/darvax/api/scan` endpoint. No new route on either side going in — pure
frontend composition, same as AUX-7 itself, gated by an out-of-order-
response guard (a `scanRequestId` counter, same convention as AUX-6's
`checkCrossLink`) so a slow response for a superseded symbol can never
clobber a card that has since moved on.

**A real inconsistency the owner caught from two side-by-side screenshots,
fixed same day.** DarvaX's `/darvax/api/scan` deliberately runs no
DAR-CARD classification (its own docstring: "adding no methodology of its
own") — it only produces a raw `DarvaxSignal`, not the tier/action-
classified `ScreenResult` a full universe sweep produces. So "Look up"
(reading a real sweep's `ScreenResult`) and "Scan & Validate" (calling
`/scan`) rendered two visibly different shapes for the identical symbol —
`TIER`/`ACTION`/`BUY ABOVE`/`STOP LOSS` versus a thinner `SIGNAL`/`RULE`
reading — confusing on one page with one search box. Root cause understood
before touching code: the classification step already exists as a pure,
already-tested function (`screen_signal` in
`src/athena/darvax/screening/engine.py`), needing only the one signal
`/scan` already produces. Fixed by wiring that exact function into
`/darvax/api/scan`'s handler and returning its result in a new, purely
additive `screened` field (a placeholder, never-persisted sweep id, since
this reading is never written to the sweep table) — no schema change, no
invented methodology, and no effect on DarvaX's own existing "Scan
symbols" UI (which already ignores the per-signal response shape
entirely). Symbol 360 now renders a fresh scan through the same row branch
"Look up" uses, with an explicit "freshly scanned, doesn't know about any
position you hold" disclosure rather than presenting it as equivalent to
a completed sweep.

Sixteen tests in `tests/darvax/test_aux8_scan_validate.py`, four proven
non-vacuous: both lanes' endpoint calls and payload shapes, the
concurrency (`Promise.all`, not sequential), the out-of-order-response
guard on both lanes, a new lookup invalidating an in-flight scan, and —
the two backend-level ones, hitting the real route over real (fake-
market-data) candles rather than a source grep — that `/darvax/api/scan`
actually returns a classified `screened` result and that it is never
persisted as a real sweep. Full suite 2,181 passing (2,165 -> 2,178 initial
-> 2,181 after the classification fix). Live-verified end-to-end on an
isolated scratch server: the real candidate-upsert → validate → Kite
ingest → fresh Decision sequence and the real DarvaX scan both completed
successfully and rendered correctly in one click; a follow-up "Look up"
for a different symbol correctly reset the scan state. See
`IMPLEMENTATION_SUMMARY.md`'s AUX-8 entry for full detail.
**Owner-approved 2026-08-21.**

The approved AUX-3 design record remains at
[`docs/design/ATHENA-DECISION-LIST-CONFIDENCE-DESIGN.md`](design/ATHENA-DECISION-LIST-CONFIDENCE-DESIGN.md).
The approved freshness and cycle foundations remain documented in
[`docs/design/ATHENA-ADVISORY-FRESHNESS-DESIGN.md`](design/ATHENA-ADVISORY-FRESHNESS-DESIGN.md).

## Phase 0 — Foundations ✅ APPROVED (2026-07-20)

Delivered as one batch before this workflow existed; retroactive milestone map:
M0.1 Repository & Project Setup · M0.2 Canonical Domain Model · M0.3 Configuration
Framework · M0.4 Trading Calendar · M0.5 Observability & CLI.

## Phase 1 — Data Foundation ✅ APPROVED (2026-07-20)

| Milestone | Scope | Status |
|---|---|---|
| **M1.1** MarketDataProvider Contracts | Provider Protocol hardening, ProviderCapabilities, ProviderHealth, behavioral contract, reusable contract test suite | ✅ Approved |
| **M1.2** FileProvider | FileProvider; daily/intraday/instrument/quote loaders; provider health | ✅ Approved |
| **M1.3** Validation Layer | Freshness, OHLC, duplicate, gap validation; validation reports; quarantine handling | ✅ Approved |
| **M1.4** Corporate Actions Engine | Splits, bonuses, dividends, renames; historical adjustment strategy | ✅ Approved |
| **M1.5** SQLite Repository | Schema, WAL, foreign keys, repository layer, append-only storage, integrity verification | ✅ Approved |
| **M1.6** Backup & Restore | Backup, restore, recovery validation, repository recovery tests | ✅ Approved |

## Phase 2 — Market Intelligence ✅ APPROVED (2026-07-21)

| Milestone | Scope | Status |
|---|---|---|
| **M2.1** Regime Engine | Deterministic regime (trend/volatility/gap) with evidence | ✅ Approved |
| **M2.2** Market Health | Breadth, trend quality, participation, momentum, volatility health | ✅ Approved |
| **M2.3** Sector Health | Sector-level strength, deterministic + explainable | ✅ Approved |
| **M2.4** Universe Engine | Investable universe construction with explainable inclusion | ✅ Approved |

## Phase 3 — Decision Intelligence ✅ APPROVED (2026-07-21)

| Milestone | Scope | Status |
|---|---|---|
| **M3.1** Evidence Aggregation | Single immutable evidence graph with provenance + missing detection | ✅ Approved |
| **M3.2** Indicator Engine | Deterministic technical indicators (SMA/EMA/RSI/ATR/MACD/ADX/vol avgs) | ✅ Approved |
| **M3.3** Scoring Engine | Transparent component scores from approved evidence/indicators | ✅ Approved |
| **M3.4** Confidence Engine | Evidence reliability (completeness, agreement, freshness, contradictions) | ✅ Approved |
| **M3.5** Risk Engine | Descriptive trading-risk assessment (volatility/liquidity/gap/event/concentration) | ✅ Approved |
| **M3.6** Decision Engine | First explainable decisions from bundle+indicators+scores+confidence+risk | ✅ Approved |
| **M3.7** Decision Trace & Reporting | Human + machine-readable decision reports | ✅ Approved |

## Phase 4 — Orchestration & Operational Intelligence ✅ APPROVED (2026-07-21)

Turns the analytical core into an operational platform; consumes Phase 0–3 engine outputs only, modifies no analytical engine.

| Milestone | Scope | Status |
|---|---|---|
| **M4.1** Workflow Orchestration Engine | Deterministic DAG pipeline runner (stages, execution, report, failure isolation, replay) | ✅ Approved |
| **M4.2** Daily Market Scanner | Run ATHENA across the universe → DailyScanReport | ✅ Approved |
| **M4.3** Watchlist Manager | Dynamic watchlists from decision outcomes | ✅ Approved |
| **M4.4** Strategy Framework | Deterministic strategies consuming DecisionReport | ✅ Approved |
| **M4.5** Backtesting Engine | Historical replay through the full pipeline | ✅ Approved |
| **M4.6** Reporting & Analytics | Daily/weekly/monthly summaries + statistics | ✅ Approved |
| **M4.7** Scheduling Framework | Daily/weekly/manual/replay/batch job scheduling | ✅ Approved |

## Phase 5 — Portfolio & Execution Platform ✅ APPROVED (2026-07-21)

Manages capital responsibly; consumes completed Decision artifacts produced by the existing pipeline; performs no market analysis.

| Milestone | Scope | Status |
|---|---|---|
| **P5.1** Portfolio Engine | Deterministic portfolio state, holdings, cash allocation, reserved capital, closed positions | ✅ Approved |
| **P5.2** Capital Allocation Engine | Capital allocation policy and reserve floor enforcement | ✅ Approved |
| **P5.3** Position Sizing Engine | Executable unit quantity calculation & precision handling | ✅ Approved |
| **P5.4** Order Planning Engine | Broker-neutral execution instructions & order batching | ✅ Approved |
| **P5.5** Broker Abstraction Layer | Canonical broker contracts & capability validation | ✅ Approved |
| **P5.6** Order Lifecycle Engine | Order tracking, fill reconciliation, state machine | ✅ Approved |
| **P5.7** Portfolio Analytics & Performance | Realized P&L, performance metrics, portfolio statistics | ✅ Approved |

## Phase 6 — Reporting, Dashboards & User Intelligence ✅ APPROVED (2026-07-21)

Presents, organizes, and explains information already produced by the core platform; read-only; no state mutation.

| Milestone | Scope | Status |
|---|---|---|
| **P6.1** Reporting Framework | Generic operational reporting engine (portfolio, execution, allocation, analytics, audit) | ✅ Approved |
| **P6.2** Dashboard & Snapshot Engine | Derived, read-only dashboard views & snapshots | ✅ Approved |
| **P6.3** Explainability Engine | Human-readable decision & performance explanations | ✅ Approved |
| **P6.4** Timeline & Audit Engine | End-to-end pipeline audit reconstruction & timelines | ✅ Approved |
| **P6.5** Operational Monitoring | Execution pipeline & component health observing | ✅ Approved |
| **P6.6** Export & Presentation Layer | Deterministic presentation formatting & export | ✅ Approved |
| **P6.7** Unified Intelligence Workspace | Read-only operational workspace orchestration | ✅ Approved |

## Phase 7 — Production Orchestration & Scheduling ✅ APPROVED (2026-07-21)

Integrated runtime orchestration layer linking all pipelines and job schedules.

| Milestone | Scope | Status |
|---|---|---|
| **P7.1** Generic Pipeline Infrastructure | Immutable models for stage execution, context propagation, definition, and history | ✅ Approved |
| **P7.2** Execution Pipeline Registration | Dual-root execution topology combining portfolio, capital allocation, sizing, and analytics | ✅ Approved |
| **P7.3** Intelligence Pipeline Registration | Wiring 6 presentation/intelligence stage adapters under declarative topology | ✅ Approved |
| **P7.4** Pipeline Runner Integration | PipelineContract validation, PipelineCoordinator, WorkspaceAssembler, and SystemPipelineRunner | ✅ Approved |
| **P7.5** Pipeline Scheduler Registration | Scheduling-domain bridge adapter wrapping ScheduledJob, ScheduleRunRequest, and history | ✅ Approved |

## Phase 8 — Application Platform ✅ APPROVED (2026-07-22)

Exposes internal pipeline artifacts, execution records, portfolios, and reports through a production-grade REST API.

| Milestone | Scope | Status |
|---|---|---|
| **P8.1** Platform API Foundation | FastAPI integration, ASGI/Lifespan lifecycle, unified response envelope, Problem Details, Health/Metrics | ✅ Approved |
| **P8.2** Authentication & RBAC | Users, Roles, Permissions, JWT, API Keys, Sessions, Audit Logging | ✅ Approved |
| **P8.3** Core Platform APIs | Decisions, Portfolios, Pipelines, Scheduler, and Workspace endpoints | ✅ Approved |
| **P8.4** Reports, Analytics & Export APIs | Generic Reports, Portfolio Analytics snapshots, and file format exports | ✅ Approved |
| **P8.5** API Platform Completion | Versioning, metadata endpoints, request context middleware, audit logger, and OpenAPI audit | ✅ Approved |

## Phase 9 — Dashboard & Operations Console (COMPLETE)

Builds the visual workstation dashboard console for a single-user Swing/Intraday trading platform.

| Milestone | Scope | Status |
|---|---|---|
| **P9.1** Dashboard Architecture | Static asset hosting, fallback routing, dashboard HTML/CSS workstation layout | ✅ Approved |
| **P9.2** Consolidated Dashboard API | High-performance aggregated summary endpoint, sidebar & header telemetry integrations | ✅ Approved |
| **P9.3** Portfolio & Capital Dashboard | NAV area line chart, Sector Exposure donut, Holdings grid, and single-user bypass | ✅ Approved |
| **P9.4** Market & Universe Dashboard | Trading calendar session grid, Volatility regime badges, Universe inclusion traces | ✅ Approved |
| **P9.5** Strategy & Backtest Workspace | Strategy profiles matrix, Backtest performance metrics & drawdown charts | ✅ Approved |
| **P9.6** Decision Trace DAG Viewer | Briefing documents browser, interactive Decision Trace React Flow DAG viewer | ✅ Approved |
| **P9.7** Live Monitoring & Admin | SSE live warning streams, stage telemetry bar charts, manual DB backup/restore controls | ✅ Approved |

**Phase 9 closed (2026-07-23):** owner approved P9.7; console hotfixes and Overview correctness patches remain recorded in `IMPLEMENTATION_SUMMARY.md`.

## Phase 10 — Live Dry-Run Operations & AI Playbook Learning (COMPLETE)

Establishes live scheduled paper-trading operations, real-time market data ingestion, daily trace briefings, and automated playbook diagnostics. One milestone in flight at a time.

| Milestone | Scope | Status |
|---|---|---|
| **M10.1** Live Data Ingestion | Real-time broker/feed Quote and Candle ingestion, duplicate/freshness validation in live loop | ✅ APPROVED |
| **M10.2** Scheduled Dry-Run Operations | Premarket and periodic intraday refresh cycles running daily on scheduler, logging to SQLite | ✅ APPROVED |
| **M10.3** Daily Briefing Notifications | Automated email/webhook notifications dispatching daily decision traces and summaries | ✅ APPROVED |
| **M10.4** AI Playbook Diagnostics | Diagnostic analysis over Decision Journal outcomes, proposing configuration weight tuning suggestions | ✅ APPROVED |

**Phase 10 closed (2026-07-23):** owner approved M10.4. Production readiness for daily advisory use continues under [`docs/PRODUCTION_READINESS_ROADMAP.md`](PRODUCTION_READINESS_ROADMAP.md) tracks R1–R6 (not authorized until owner gates each item).

### Production readiness track

| Milestone | Scope | Status |
|---|---|---|
| **R1** File-backed Daily Ops SOP | SOP + smoke script for file-backed mock trading day | ✅ APPROVED |
| **R2** Decision Journal Persistence | Persist decisions/traces for OK briefings | ✅ APPROVED |
| **R3–R6** | See production readiness roadmap | R3–R6 ✅ APPROVED |

SOP: [`docs/ops/FILE_BACKED_DAILY_OPS.md`](ops/FILE_BACKED_DAILY_OPS.md) · Smoke: `./scripts/smoke_file_backed_day.sh`

#### Fix pass: host scheduler ran REFRESH/CLOSING cycles on weekends/holidays (owner-reported, 2026-08-01)

**Root cause, confirmed against the live database:** every one of 24 pipeline
runs on 2026-08-01 (a Saturday) failed with the identical error —
`ingest rejected dataset 'quotes': FRESHNESS: quotes are N min behind as_of
(threshold 20 min)`, with `N` growing linearly with wall-clock time. Kite's
`/quote` API correctly returns the last real trade (Friday 2026-07-31, 3:30
PM IST market close) — there is no fresher quote to have on a day the
exchange isn't open. The actual bug: `is_premarket_due()`/`is_refresh_due()`/
`is_closing_due()` (`src/athena/scheduling/cadence.py`) only ever checked
wall-clock time-of-day against configured session hours; nothing in the path
the host's ~15-minute cron (`athena run-due` → `HostDueRunner`) takes ever
consulted `CalendarEngine` — the module explicitly documented elsewhere as
"the sole trading-day/session authority" — to check whether the day itself
was even a trading day. Every non-trading day, the scheduler fires cycles
all day that are destined to fail, which also degrades unrelated features by
flooding `runs` with noise (this is the same root cause behind the earlier
"Showing 0" Validation Workbench bug this session — a losing streak of
failed runs pushes the last real successful run out of the frontend's
recent-runs window).

**Fix:** added an explicit `is_trading_day: bool = True` parameter to all
four cadence functions (default preserves every existing caller's exact
prior behavior — this is additive, not a breaking signature change).
`HostDueRunner` now accepts an optional, injectable `calendar`/`config_dir`
(matching the existing `pipeline` injection pattern) and resolves
`is_trading_day` from `CalendarEngine.context_for(as_of.date()).session_type`
before calling `due_triggers()`, suppressing all three trigger types on
`WEEKEND`/`HOLIDAY`. The diagnostic `athena due` CLI command was updated the
same way and now also prints the resolved `session` type.

Architectural note: this is a scheduling/ops bug fix, not a scoring, domain,
or frozen-contract change — it wires an already-existing, already-approved
calendar authority into a caller that should have consulted it but didn't.
No ADR required.

Validation note: full suite — 1,160 passed (8 new tests: 5 in
`tests/runtime/test_dry_run_schedule.py` locking the `is_trading_day=False`
suppression on all 4 functions plus the default-`True` backward-compat case;
3 in `tests/ops/test_host_ops.py` locking `HostDueRunner`'s calendar
resolution, including the no-calendar-wired backward-compat path). Ruff
clean. Live-verified against the real, running environment (not just
synthetic tests) via `PYTHONPATH=src python3 -c "...athena.cli main()..."`
with `due` on today's real date: reports `session: WEEKEND`, `due: (none)` —
confirming the fix engages correctly against the actual current calendar
config and actual current time, not a mock.

### Dashboard ops extensions (post Phase 9/10)

| Milestone | Scope | Status |
|---|---|---|
| **D-P1** Portfolio reset | Reset open \| all owner fills with ADMIN + CONFIRM | ✅ Approved |
| **D-V1** Owner candidate list | SQLite `owner_candidates` + MI CRUD, shared with CLI | ✅ Approved |
| **D-V2** Eligibility in cycle | UniverseEngine on candidates → real Eligible/Excluded | ✅ Approved |
| **D-V3** Qualify WATCH/TRADE | Scan eligible → persist decisions; MI qualified-today | ✅ Approved |
| **D-U1–U3** Nifty 500 seed | Daily merge-unique Nifty 500 → `owner_candidates` | ✅ Approved |

**Dashboard ops extensions track closed (2026-08-01):** owner approved all
five milestones on the strength of a 2026-08-01 re-verification against the
current codebase (42 tests passed across `test_owner_portfolio.py`,
`test_owner_candidates.py`, `test_owner_validation.py`,
`test_candidate_seed.py`; see IMPLEMENTATION_SUMMARY.md's "Nifty 500 daily
candidate seed" and "Portfolio reset + owner validation list" entries).

### Professional live-entry track (post Phase 9/10)

| Milestone | Scope | Status |
|---|---|---|
| **M-E1** Auth surface | Owner env seed, unlock UI, JWT login/refresh/logout/me | ✅ Approved |
| **M-E2** Workstation host | `athena serve`, optional due-cycle worker, shared runner lock | ✅ Approved |
| **M-E3** Kite morning gate | Verified read-only session, in-UI authorize/exchange/reconnect | ✅ Approved |
| **M-E4** macOS Dock launcher | Thin `.app` wrapper + installer; health-aware open/start | ✅ Approved |
| **M-E5** Hardening & ops polish | Login lockout, JWT hardening, optional TLS, live-entry SOP, QA verification | ✅ Approved |

**Professional live-entry track closed (2026-07-24):** owner approved M-E5;
the complete Dock/URL → unlock → Kite → LIVE workflow is operational.

### Instrument decision brief track (post Phase 9/10)

| Milestone | Scope | Status |
|---|---|---|
| **M-D1** Decision Brief foundation | Selected-stock brief, TradePlan presentation, non-destructive daily dismiss | ✅ Approved |
| **M-D2** Chart + plan overlays | Read-only candles API, intraday chart, entry/stop/target overlays, freshness; after-hours validate clamps to last session close | ✅ Approved |
| **M-D3** ATHENA depth | Eligibility, decision timeline, score/confidence/risk detail, re-validate/remove candidate | ✅ Approved |
| **M-D4** Context lane | Session events, deterministic brief export, approved external context links | ✅ Approved |
| **M-D5** News evidence | Provenance-first news annotation after DD-5/provider approval | ⏸ Deferred |

**Instrument decision brief track closed (2026-07-25):** owner approved M-D4
after live smoke-test review (regime/market-health persistence, external
links, Decision Brief export, Reasoning Trace DAG redesign, header
Re-validate). M-D5 remains deferred until DD-5/provider approval.

---

### Symbol Chart Excellence track (owner direction, 2026-07-29)

World-class symbol chart presentation for the Decision Brief, governed by
`docs/design/ATHENA-SYMBOL-CHART-ROADMAP.md`. This track improves chart
inspection quality only; it does not change ATHENA scoring, create orders,
invent signals, or add broker write behavior. ADR-004 already permits static
HTML/vanilla JS/Lightweight Charts on this surface, and ADR-005 governs every
overlay as data.

| Milestone | Scope | Gate | Status |
|---|---|---|---|
| **CH-0** Design & architecture gate | Current chart audit, target experience, staged roadmap, no-fabrication/no-order-placement boundaries | Owner approval of roadmap and chart-library dependency approach | ✅ Approved (2026-07-29) |
| **CH-1** Professional chart foundation | Reusable professional chart controller over the existing candles endpoint; candles, volume, SMA, responsive normal/modal views, latest-price marker, aligned asset cache-busters | None — implemented with local static JS/CSS, no new dependency | ✅ Approved (2026-07-29) |
| **CH-2** TradePlan overlays & validity layer | Entry band, stop/target price lines with percentage deltas, risk/reward chip, and expiry/freshness affordance from existing plan data | None | ✅ Approved (2026-07-29) |
| **CH-3** Timeframe, range, and session controls | Configured 5m/15m timeframe controls in embedded/modal charts, local chart preference, session separators, requested-vs-returned bar counts, timeframe-specific no-data wording, visible last-candle timestamp | None | ✅ Approved (2026-07-29) |
| **CH-4** Interactive inspection | Crosshair OHLCV legend, rendered indicator readouts, plan-level readouts, reset affordance, keyboard focus/accessibility pass, enlarged dedicated chart modal | None | ✅ Approved (2026-07-29) |
| **CH-5** Decision & event markers | Persisted decision/journal/outcome markers on the chart; revalidation markers deferred until a persisted timestamp is exposed | Additive read-only endpoint only if existing payloads are insufficient; ADR required for frozen contract/domain expansion | ✅ Approved (2026-07-29) |
| **CH-6** Resilience, visual QA, and release gate | Release-gate regression tests for nonblank rendering, no-data/fallback states, interaction wiring, modal no-scroll layout, persisted-only markers, and max-limit budget contracts | Owner review after QA evidence | ✅ Approved |

**Implementation rule:** CH-0 must be owner-approved before CH-1 starts; after
that, exactly one chart milestone is implemented and reviewed at a time.

**Symbol Chart Excellence track closed (2026-08-01):** owner approved CH-6,
the last of the 7 milestones (CH-0 through CH-6), on the strength of a
2026-08-01 re-verification against the current codebase (release-gate test
suite re-run, 5 passed; see IMPLEMENTATION_SUMMARY.md's CH-6 entry). The
symbol chart is a hardened, resilience-tested trading decision surface —
nonblank rendering, no-data/fallback states, stable interaction wiring,
no-scroll modal layout, persisted-only markers, and rendering-budget limits
are all regression-locked.

---

### Advisor Status Layer track (owner direction, 2026-07-29)

Moves Decisions & Trace from an engineering-console feel toward an intraday
advisor surface. Presentation-only: consumes existing ticker/session/telemetry,
selected-decision, and TradePlan freshness data; does not change scoring,
risk, decision policy, providers, frozen domain contracts, or order behavior.

| Milestone | Scope | Gate | Status |
|---|---|---|---|
| **AS-0** Advisor status plan | Audit screenshot, define actionability states, diagnostics boundary, pulse-strip content, staged rollout | Owner approval | ✅ Approved (2026-07-29) |
| **AS-1** Header pulse + actionability foundation | Replace always-visible REQ/CORR/LATENCY with advisor pulse + diagnostics popover; add selected-symbol actionability banner that can override a green BUY-looking setup when market/plan state makes it non-actionable | None — frontend presentation over existing data only | ✅ Approved (2026-07-30) |
| **AS-2** Freshness propagation | Add plan/actionability state to Quick Summary and the symbol list so expired/stale plans are visible before opening each brief | None — reuse selected/list payloads and plan freshness where available; no fabricated timestamps | ✅ Approved (2026-07-30) |
| **AS-3** Market closed review mode | Surface market-closed/next-session messaging and review-mode wording across header and detail pane once existing calendar/session data is exposed to the dashboard | Additive read-only API only if existing payloads are insufficient | ⚠️ Implemented; full-suite blocked by local disk capacity |
| **AS-4** Release gate | Regression tests for diagnostics privacy, actionability overrides, reduced-motion pulse behavior, and expired-plan visual dominance | Owner review after QA evidence | ✅ Approved (2026-07-30) |

**Implementation rule:** one AS milestone at a time. AS must never create
trading signals, alter ATHENA's recommendation, or imply order execution.

#### AS-1 — header pulse + actionability foundation (approved, 2026-07-30)

Scope completed: the primary header now uses an advisor pulse strip for
market/Kite/selected-plan messages, while exact `REQ-ID`/`CORR-ID`/latency
remain available in a diagnostics popover. Selected TradePlans now render an
Advisor Status banner in the Decision Brief header. If the plan is expired or
stale, the banner and pulse explicitly say the setup is not actionable /
requires re-validation before any manual action, without changing the
underlying ATHENA recommendation. Reduced-motion users get a static truncated
pulse message instead of scrolling text.

Owner screenshot review fix pass: the AS-1 header pulse was tightened to avoid
duplicating the market ticker, the diagnostics popover was compacted, and the
expired-plan banner was restyled with shorter action-first wording so the
advisor warning does not read like loose body copy.

Deferred deliberately at AS-1 close: propagating plan freshness into every
left symbol row and adding it to Quick Summary moved to AS-2; showing a real
market-closed / next live-session date remains AS-3. AS-1 does not fabricate a
next session from browser time; that must come from ATHENA's calendar/session
authority.

#### AS-2 — freshness propagation (approved, 2026-07-30)

Scope completed: the Decisions symbol list now shows a compact TradePlan
freshness chip per row (`Valid`, `Aging`, `Stale`, `Expired`, or `No plan`)
before opening the brief. Quick Summary now includes a `Plan Status` row using
the same freshness wording. The selected brief first infers status from the
persisted TradePlan validity window, then refreshes Quick Summary with the
authoritative `/plan-freshness` DTO after it loads.

Architectural note: AS-2 is frontend presentation only. It does not alter
decision type, score, confidence, risk, TradePlan values, providers, schemas,
or broker behavior. List-row freshness uses only persisted `valid_from` /
`valid_until` and the same configured freshness fractions as the backend
service (`0.5` warn, `0.8` stale); the selected brief remains authoritative via
the existing API DTO.

#### AS-3 — market closed review mode (implemented; validation blocked, 2026-07-30)

Scope completed: the dashboard now exposes a read-only
`/api/v1/dashboard/session-status` endpoint that computes live/review-mode
exchange status from `CalendarEngine` and configured NSE session times. The
header advisor pulse now shows server-provided market closed / next-live
wording outside live hours. The selected Decision Brief Advisor Status banner
switches valid plans into review mode when the market is closed, while expired
and stale plan warnings remain stronger and continue to require re-validation.

Architectural note: AS-3 adds only a read-only dashboard DTO/endpoint and
presentation wiring. It does not change scoring, risk, decision policy,
TradePlan values, provider behavior, schemas used by analytical engines, or
broker behavior. The next-live date is computed by the backend from ATHENA's
calendar/session authority; the frontend never fabricates market dates.

Validation note: focused API/dashboard checks pass, but the full suite is
blocked on this machine because the filesystem is effectively full
(`db/` is ~9.8 GiB; only ~115 MiB free), causing unrelated SQLite `disk I/O
error` failures in repository tests and live-repo-backed shape tests.

#### AS-4 — advisor status release gate (approved, 2026-07-30)

Scope completed: added a dedicated Advisor Status release-gate regression test
for diagnostics privacy, reduced-motion pulse behavior, actionability
dominance, and expired-plan visual dominance. The gate locks in that REQ-ID /
CORR-ID / latency remain hidden behind the diagnostics popover; reduced-motion
users receive a static ellipsis pulse; expired/stale TradePlans outrank
market-closed review mode and green "plan valid" wording; and historical
expired TRADE records stay out of the current Decisions board rather than
becoming restorable dismissals.

Owner live-review fix pass: scoped revalidation that excludes a symbol now
surfaces a no-current-TradePlan warning instead of silently falling back to an
old decision; expired historical TradePlans are labeled as historical/not
actionable in the cockpit, Quick Summary, eligibility section, and TradePlan
card. The original persisted decision remains available for audit/replay, but
the left rail is now a current action board only.

Architectural note: AS-4 is presentation/test hardening only. It does not
change ATHENA's scoring, confidence, risk, decision policy, TradePlan values,
providers, schemas, frozen domain contracts, or broker behavior.

Validation note: focused dashboard checks pass (`tests/api/platform/
test_dashboard_hosting.py`), but the full suite remains blocked locally by
critically low disk space (hundreds of MiB free on a repository with a ~9.8 GiB
live `db/`).

**Advisor Status Layer track closed (2026-07-30):** owner approved AS-4. The
Decisions & Trace advisor surface now has release-gated diagnostics privacy,
market/revalidation actionability wording, expired-plan dominance, and a
current-action-board contract for the left rail.

---

### Intraday Advisor UX track (owner direction, 2026-07-30)

Turns ATHENA's intraday recommendation surface into an explicit manual trading
workflow. Presentation-only unless a later milestone states an additive
read-only API need. This track does not change scoring, risk, decision policy,
TradePlan values, providers, frozen domain contracts, or broker behavior.
Governing plan: `docs/design/ATHENA-INTRADAY-ADVISOR-UX-ROADMAP.md`.

| Milestone | Scope | Gate | Status |
|---|---|---|---|
| **TP-1** Trade Playbook foundation | Move symbol revalidation into Advisor Status; add selected-symbol Trading Steps with entry/stop/target/no-fill/expiry/close/revalidation rules | Owner review after UX/test evidence | ✅ Approved |
| **TP-2** Current Board controls | Add Re-validate Visible for current-board symbols with progress/result summary | Owner review; must not validate hidden historical rows | ✅ Approved |
| **TP-3** Top Current Setups | Add top 10 current valid/aging setups sorted by existing score/confidence/risk/return data | Owner review; no expired/stale/no-plan rows | ✅ Approved |
| **TP-4** Intraday SOP surface | Add persistent intraday SOP/help surface for day workflow and manual execution boundaries | Owner review | ✅ Approved |

**Implementation rule:** one TP milestone at a time. TP must never create order
placement, broker write actions, new signals, or changes to ATHENA's analytical
engines.

#### TP-1 — trade playbook foundation (approved 2026-08-01, built 2026-07-30)

Scope completed: symbol-specific `Re-validate` moved from the generic
Decision Brief header into Advisor Status, where the stale/expired/review-mode
reason is visible next to the corrective action. The setup tab now includes a
Trading Steps panel before TradePlan levels, covering entry, stop, target,
no-fill, end-of-day, and re-check rules. The panel adapts wording for current
plans, market-closed review mode, and expired historical plans without
changing ATHENA's underlying recommendation or persisted TradePlan values.
Owner-review usability pass initially added a scroll-aware compact cockpit, but
AW-4 replaced that with a steadier detail shell: only the selected
symbol/current-price row stays fixed, while metadata, gauges, Advisor Status,
tabs, and active tab content scroll together. This avoids scroll flicker on
short tabs such as Market Context.

Architectural note: TP-1 is presentation-only over existing Decision,
TradePlan, freshness, quote/session, and validation state. It does not add
orders, broker write actions, new signals, scoring/risk/decision changes, or
domain/API contract changes.

Validation note: focused dashboard hosting checks pass. The full suite remains
deferred locally until the live DB/storage pressure is cleaned up.

Owner screenshot fix: the main card summary was reduced from three cramped
mini-cards to a single compact status strip; blocker text on the card now uses a
short plain label while preserving exact rule evidence inside the modal; the
workbench modal explicitly overrides the shared 600px modal cap, resets to
Overview, and scrolls to the top every time View Details opens.

Second owner screenshot fix: Qualified Today rows no longer render duplicate
decision chips (`TRADE TRADE`). Each row now shows one decision chip plus Open
decision and Save/Saved actions, using the existing deterministic Decisions
selection flow and Saved Symbols service.

Third owner screenshot fix: the next-action summary now spans the full
Validation Pipeline card width and wraps normally, avoiding the clipped
`Review 177 current T...` state.

Fourth owner fix: Open decision now clears Decisions filters, uses a strict
symbol-selection load, and refuses to silently fall back to another symbol.
Validation reports disable Open decision when the latest validation outcome has
no current decision row to open, including Excluded outcomes.

**Docs-accuracy re-verification (2026-08-01):** re-checked against the current
codebase rather than trusting this write-up's age. `renderTradePlaybook()`/
`refreshTradePlaybook()` (`js/13-decision-brief-core.js`) and the "Trading
steps" section/CSS are all present and unchanged; the symbol re-validate
control lives in the Advisor Status banner (`index.html`), matching the scope
above. `tests/api/platform/test_dashboard_hosting.py` — 4 passed. Git:
`b025b8b feat(decision): enhance intraday advisor playbook and Trade Plan
cockpit` (2026-07-30), with five follow-on commits building further on top
without reverting it. No order-placement/broker-write code found in any
touched file. **Owner approved 2026-08-01** on the strength of this evidence.

#### TP-2 — current board controls (approved 2026-08-01, built 2026-07-30)

Scope completed: the Decisions left rail now includes a `Re-validate visible`
control for the on-screen current-board rows in the left list viewport. It
collects only row symbols intersecting the visible scroll area, reuses the
existing scoped validation workflow, shows the same blocking validation
overlay, refreshes the workspace after completion, and writes a result strip
with validated count plus Trade/Watch/No trade/Excluded summary. Failed
validation leaves an explicit warning that existing rows should be treated as
stale until retry. Owner live test fixes capped long validation symbol lists in
the overlay/toast and corrected the visible-row batch from "all rendered rows"
to actual viewport-visible rows, avoiding 300+ symbol multi-minute runs from
the left-rail shortcut. Follow-up live test fix capped the quick action to the
first 5 on-screen rows because scoped validation is a synchronous ingest +
eligibility + decision cycle; larger batches belong in a dedicated/background
flow, not the quick refresh affordance.
Every quick refresh outcome now starts a 60-second local cooldown, preventing
habitual repeat taps from reaching Kite's rate limit in normal use. Kite
429/rate-limit responses are mapped to plain user copy and use the same
cooldown. The button is disabled during cooldown, switches to an hourglass, and
its tooltip/accessible label carries the retry countdown. Larger refreshes
remain intentionally out of scope for this shortcut and should use a
dedicated/background flow.
The validation overlay now includes an elapsed timer and a close control. Close
hides the progress screen only; the already-started validation continues and
the left-list status strip reports the result/cooldown.
Cooldown-only status messages clear automatically when cooldown ends. Actual
error/rate-limit guidance stays visible until the next user action.

Architectural note: TP-2 is frontend orchestration over the existing scoped
candidate validation endpoint. It adds no broker write action, no order
placement, no analytical engine change, and no new recommendation logic.
Hidden historical expired TradePlans are not present in the rendered current
board and are therefore not included in the visible-symbol batch.

Validation note: focused dashboard hosting checks pass. The full suite remains
deferred locally until the live DB/storage pressure is cleaned up.

**Docs-accuracy re-verification (2026-08-01):** `#decisions-revalidate-visible-btn`
and `revalidateVisibleDecisionBoard()` (`js/12-decisions-list.js`) are present
and unchanged. `tests/api/platform/test_dashboard_hosting.py` — 4 passed.
Git: `0d2d72f feat(dashboard): add visible-board revalidation control`
(2026-07-30) touches exactly the files this scope claims. **Owner approved
2026-08-01** on the strength of this evidence.

#### TP-3 — top current setups (approved 2026-08-01, built 2026-07-30)

Scope completed: the Decisions left rail now starts with a `Top Current Setups`
review queue when current qualifying rows exist. The queue is capped at 10 and
is built only from the same filtered/dismissal-aware current-board rows already
visible to the owner. Admission is deliberately strict: a row must still be an
actionable `TRADE` with a `FRESH` or `AGING` TradePlan. Expired, stale,
no-plan, historical, dismissed, and filtered-out rows cannot enter the top
queue. Ranking is presentation-only over existing persisted/display data:
score first, then confidence, lower risk, expected return, risk/reward,
timestamp, and symbol. The normal Trade/Watch/No trade sections remain below
the queue for complete board context.

Owner UX adjustment: the long left-list explanation was compacted into a short
count line (`current · Trade · Watch · No trade`) with explanatory semantics
moved into hover/title text, preserving scan space for setup rows.

Architectural note: TP-3 adds no broker write action, no order placement, no
analytical-engine change, no TradePlan value change, and no new recommendation
logic. It is a frontend review queue over the existing current board.

Validation note: focused dashboard hosting checks pass. The full suite remains
deferred locally until the live DB/storage pressure is cleaned up.

**Docs-accuracy re-verification (2026-08-01):** `topCurrentSetups()`
(`js/12-decisions-list.js`) and the `.top-current-setups-section` CSS
(`css/12-decision-cards-dag.css`) are present and unchanged.
`tests/api/platform/test_dashboard_hosting.py` — 4 passed. Git: `a81be8e
feat(dashboard): add top current setup queue` (2026-07-30) matches this
scope exactly. **Owner approved 2026-08-01** on the strength of this evidence.

#### TP-4 — intraday SOP surface (approved, 2026-07-30)

Scope completed: ATHENA now has a persistent `Intraday operating guide`
reachable from the global header without selecting a symbol. The guide is a
modal operating manual, not another sticky panel, so it does not reduce the
selected-symbol reading area. It covers before-market checks, building the work
queue, before-entry checks, no-fill handling, after-entry handling, end-of-day
rules, and the manual broker boundary in plain language.

Owner copy requirement: the SOP avoids internal terms and uses normal trading
language such as check, skip, entry zone, stop, target, exit, and market close.
It explicitly states that ATHENA is advisory only, does not place orders, does
not guarantee profit, and leaves the final action, position size, broker order
type, and exit to the owner.

Architectural note: TP-4 is static frontend guidance only. It adds no broker
write action, no order placement, no analytical-engine change, no TradePlan
value change, no backend endpoint, and no new recommendation logic.

Validation note: focused dashboard hosting checks pass. The full suite remains
deferred locally until the live DB/storage pressure is cleaned up.

**Intraday Advisor UX track closed (2026-07-30):** owner approved TP-4, the
final approved TP milestone. The Decisions & Trace advisor workflow now has
selected-symbol trading steps, current-board refresh controls, a top current
setup review queue, and a persistent intraday operating guide. Any additional
TP work requires a new owner-approved milestone entry before implementation.

**Correction (2026-08-01):** this note was written on 2026-07-30, but TP-1,
TP-2, and TP-3 above were still `🔄 Ready for review` at the time — the
status table is always the source of truth per `ATHENA_BRIEFING.md` §5, not
this prose note, so the "track closed" framing was premature by four days.
All three were re-verified against the current codebase and approved on
2026-08-01 (see each milestone's own re-verification note above); this
closing statement is accurate now.

---

### Advisor Workbench Polish track (owner direction, 2026-07-30)

Improves the completed intraday advisor cockpit around entry readiness and
Market Intelligence validation workflows. Presentation-first unless a milestone
explicitly states an additive read-only API need. This track does not change
scoring, confidence, risk, decision policy, TradePlan values, providers, frozen
domain contracts, or broker behavior. Governing plan:
`docs/design/ATHENA-ADVISOR-WORKBENCH-POLISH-ROADMAP.md`.

| Milestone | Scope | Gate | Status |
|---|---|---|---|
| **AW-1** Entry Readiness Indicator | Compare selected live price with persisted TradePlan entry zone and show whether entry is ready, waiting, chasing, or unavailable | Owner review; no new recommendation logic | ✅ Approved |
| **AW-2** Saved Symbol Validation and Result Report | Add Saved Symbols validate action and a single-symbol validation report modal for Market Intelligence callers only | Owner review; Decision-detail revalidation must stay inline | ✅ Approved |
| **AW-3** Validation Pipeline Workbench | Revamp the Validation Pipeline card and detail modal into a daily-use validation diagnostic workbench | Owner review; no fabricated blocker data | 🔄 Ready for review |
| **AW-4** Advisor Workbench Visual QA | Screenshot/interaction QA across Decisions and Market Intelligence workbench paths | Owner review | 🔄 In progress |

**Implementation rule:** one AW milestone at a time. AW must never create order
placement, broker write actions, new signals, or changes to ATHENA's analytical
engines.

#### AW-1 — entry readiness indicator (approved, 2026-07-30)

Scope completed: the Decision Brief header now includes an entry-readiness chip
next to the live price. The chip compares the current live quote with the
selected decision's persisted TradePlan entry zone and refreshes when the
selected decision, live quote, quote clear, or authoritative plan freshness
changes. It shows `Entry ready`, `Wait for entry`, `Chasing risk`,
`No current entry`, or `Waiting for quote` using existing quote, TradePlan, and
freshness data only.
Follow-up owner safety fix: the chip no longer treats one tick above a
single-point BUY entry as automatic `Chasing risk`. It now keeps `Entry ready`
strictly for price inside the persisted entry zone, adds `Entry acceptable`
only when price is within 0.25% beyond the entry boundary and live reward:risk
from the current quote to the persisted stop/first target remains at least
1.8:1, and shows `Avoid entry` when price has already crossed the stop or
target boundary. No TradePlan values, thresholds, score, or recommendation
logic are changed.

Architectural note: AW-1 is frontend presentation only. It adds no broker write
action, no order placement, no analytical-engine change, no TradePlan value
change, no backend endpoint, and no new recommendation logic.

Validation note: focused dashboard hosting checks pass. The full suite remains
deferred locally until the live DB/storage pressure is cleaned up.

#### AW-2 — saved symbol validation and result report (ready for review, 2026-07-30)

Scope completed: Saved Symbols rows now include a `Validate` action. Market
Intelligence single-symbol validations (Saved Symbols, Universe row validate,
and Add & validate) opt into a validation report modal after the existing
validation workflow refreshes Market Intelligence and Decisions. The report
summarizes the symbol, validation time/mode, outcome, score, confidence, risk,
plan status, and useful next actions: open decision, inspect trace, save/remove
saved symbol, re-validate, or close.

Owner review fix: Saved Symbols row actions are now icon-only with tooltips and
accessible labels so the side rail no longer scrolls horizontally. The report
modal was widened and rebalanced: score/confidence/risk use compact metric
cards, plan status spans the full row to avoid truncation, and the action grid
has consistent spacing. `Open decision` now waits for the Decisions tab load and
then selects the validated symbol explicitly, preventing the previous race where
the tab switched but the symbol was not selected.

Owner UX rule preserved: Decision detail revalidation does not open the report
popup. Visible-board refresh, batch validation, and full validation also keep
their existing summary/progress surfaces instead of opening per-symbol reports.

Architectural note: AW-2 is frontend presentation/orchestration over existing
validation, saved-symbol, universe, decision, and trace data. It adds no broker
write action, no order placement, no analytical-engine change, no TradePlan
value change, no backend endpoint, and no new recommendation logic.

Validation note: focused dashboard hosting checks pass. The full suite remains
deferred locally until the live DB/storage pressure is cleaned up.

#### AW-3 — validation pipeline workbench (ready for review, 2026-07-30)

Scope completed: the Market Intelligence Validation Pipeline card now includes
an operational summary below the funnel: latest run status/time, top blocker,
and next action. The detail modal is now a workbench with Overview, Blockers,
Symbols, and Runs sections. Overview summarizes today's conversion and next
action; Blockers groups real exclusion reasons from the loaded universe rows;
Results combines eligibility, blocker, Watch/Trade outcome, score, plan
freshness, Open decision, Save, and Trace actions into one searchable section
instead of splitting eligible/excluded rows from a separate Qualified Today
block. Runs shows recent validation run status/time.

Owner review fix: validation-report `Open decision` now enables only when the
symbol has a current, openable Decisions row. Excluded/no-current reports show a
visibly disabled action instead of a dead click. The Decisions handoff now
activates the tab without an extra fallback load, and
`loadDecisionsWorkspace()` returns the strictly selected row so valid symbols no
longer show a false "not in current Decisions list" warning.

Follow-up owner fix: strict symbol opens now select by requested symbol before
considering the previously active `decision_id`. This prevents a report opened
from Market Intelligence from switching tabs but leaving the old selected symbol
in the Decision Brief.

Workbench polish fix: the former bottom Qualified Today list is merged into the
Results section, so validation screening happens in one dense list without a
second competing subsection.

Owner screenshot fix: the workbench modal width override now lives after the
shared modal cap, so the Results grid uses the available screen width without
horizontal scrolling. Results `Open decision` now depends on a refreshed
read-only current Decisions cache; rows that are not on the current board are
disabled instead of switching tabs and failing with "not found".

Owner readability fix: the Results tab now uses self-contained result cards
instead of a table-style header/column grid. Symbol explanations wrap normally,
score is recovered from the current decision, qualified payload, or explanation
without truncating the primary screening text.

Owner screening fix: the Results tab now includes compact search, outcome
filter, plan-status filter, sort order, visible result count, and reset controls.
The controls operate only on the loaded validation/decision data in the modal, so
screening large daily lists is faster without changing validation, scoring, or
TradePlan logic. Filter and sort changes now show an inline Applying indicator
and dim the result list while the client redraws large result sets.
text, plan state is shown as a labelled card metric, and actions stay pinned to
a consistent right edge without a drifting Actions header.

Data boundary: AW-3 uses the existing `/api/v1/pipelines/validation-funnel`,
`/api/v1/pipelines/runs`, merged current-day `universe_members`,
`qualified_today`, and run metadata only. Top blockers are derived only from
persisted `exclusion_reasons` or `eligibility_summary`; if those are absent,
the UI says blocker data is unavailable. No blocker, stage, or symbol outcome is
fabricated.

Architectural note: AW-3 is frontend presentation/orchestration only. It adds no
broker write action, no order placement, no analytical-engine change, no
TradePlan value change, no backend endpoint, and no new validation logic.

Validation note: focused dashboard hosting checks pass. The full suite remains
deferred locally until the live DB/storage pressure is cleaned up.

**Status correction (2026-08-01):** the "ready for review" claim above was
premature. Live owner screenshots after this write-up found the Results tab
showing zero rows despite real eligible/trade data, its Filters & Sort
popover rendering cut off outside the modal, and the search box freezing the
UI while typing — none caught by this milestone's own verification. All were
root-caused and fixed across three rounds; see "Fix pass: 6 owner-reported
dashboard UX issues" and its "Third round" subsection later in this file, and
the corresponding entries in `IMPLEMENTATION_SUMMARY.md`. AW-3 stays
`🔄 Ready for review` — not `✅ Approved` — until the owner confirms the
third-round fixes on the live authenticated dashboard (this session could not
log in to verify directly).

#### AW-4 — advisor workbench visual QA (in progress, 2026-07-30)

Owner screenshot fix: `Watch` and `No trade` decisions with no current
TradePlan now still render the Advisor Status strip with a neutral
`No current trade plan` state and a `Re-check symbol` action. This preserves
the TP-1 placement rule that symbol revalidation belongs in Advisor Status
instead of the generic header, while ensuring non-trade symbols are still
refreshable without implying they are actionable trades.

Owner usability fix: the Decision Brief detail pane now keeps only the
symbol/current-price header row fixed. Metadata, gauges, summary, Advisor
Status, tabs, and tab content live inside one scroll region, and the old
scroll-triggered compact header behavior was removed to stop Market Context and
other short tabs from flickering or feeling stuck during vertical scroll.
Follow-up owner screenshot fix: the tab strip remains part of the same scroll
surface as a full-height normal row, not a separate sticky strip, so
`Trade Plan`, `Analysis`, `Market Context`, `Response`, and `History` are not
clipped between Advisor Status and the first detail card.

Owner priority-order fix: the `Trade Plan` tab now reads in trader action
order — `ATHENA TradePlan` levels first, then `Intraday price context`, then
`Trading Steps`, then `Portfolio impact`, with `Universe eligibility` last as
supporting audit evidence. This keeps entry/stop/target and live chart context
above internal validation details without changing any ATHENA calculations.

Owner first-fold cockpit fix: the Decision Brief no longer opens with the
full score/report stack before the actionable plan. The scroll surface now
prioritizes tabs, Advisor Status, the current TradePlan ticket, and the
intraday chart before the trading guide and supporting audit sections.
Recommendation/score/confidence/risk gauges and the ATHENA Summary remain
available below the active tab content as explanation, not as the landing
experience repeated for every symbol.

Owner long-list usability fix: the Decisions symbol rail now has an in-list
`Top` affordance that appears only after the owner scrolls meaningfully down
the current board. It scrolls the symbol list itself back to the top without
touching the selected Decision Brief or the rest of the workstation.
The Decisions symbol search now also has an inline clear affordance that
appears only while a query is active, clears the filter in one click, and
returns focus to the search field.

Owner identity placement fix: the fixed Decision Brief header now treats
exchange and real company name as their own instrument metadata row
(`NSE · COMPANY NAME`), separate from the ticker title. The identity line is no
longer part of the scrolling detail content or attached to the symbol-name
stack, so it can use the available header width and wrap cleanly without
fighting the live price/actions cluster. Because the ticker already appears as
the primary title, the metadata row does not repeat the symbol as
`NSE: SYMBOL`.

Owner correctness fix: the global advisor pulse no longer says `Market live`
just because Kite/ticker data is available. The pulse now treats
`/api/v1/dashboard/session-status` as the source of truth: open sessions show
live wording, closed/pre-open/no-session states show the server calendar
message such as `Market closed · next live 31 Jul, 09:15 AM IST`, and Kite is
only appended as connectivity context.

Validation note: focused dashboard hosting checks pass. Browser shell-load QA
confirmed the dashboard assets serve, but unlocked in-dashboard visual QA
remains pending owner-session access.

**2026-08-01 update:** the owner's own live screenshot review of the
Validation Pipeline Workbench (AW-3) — exactly the kind of QA this milestone
describes — surfaced three real defects across three review rounds (search
"Fix pass: 6 owner-reported dashboard UX issues" later in this file). This is
AW-4's visual QA process working as intended, not a separate track; status
stays `🔄 In progress` until a full pass across the remaining Decisions +
Market Intelligence workbench paths turns up nothing further.

---

### Index and Sector Intelligence track (owner direction, 2026-07-31)

Adds trustworthy broad-market and sector-index context to Market Intelligence,
then connects that context to current ATHENA setups in later review-gated
milestones. Governing plan:
`docs/design/ATHENA-INDEX-SECTOR-INTELLIGENCE-ROADMAP.md`.

Agent continuity snapshot: `docs/ATHENA-IX-HANDOFF.md`. Verify this dated
handoff against this milestone table, `IMPLEMENTATION_SUMMARY.md`, and git
before continuing the IX track.

This track is presentation-only until a separately approved evidence review and
ADR authorize analytical use. It does not silently resolve SD-2, activate
`sector_quality`, alter scoring/decision thresholds, or add broker write paths.

| Milestone | Scope | Gate | Status |
|---|---|---|---|
| **IX-1** Tracked-Index Data Foundation | Separate quote-only snapshot coverage from benchmark history ingestion; add validated index catalog and read-only API | Owner review; no scoring/domain/protocol change | ✅ Approved |
| **IX-2** Index Leadership Surface | Compact, session-aware broad-market and sector leadership view in Market Intelligence | Owner review and visual QA | ✅ Approved |
| **IX-3** Versioned Constituents and Index Breadth | Official provenance-tagged memberships, resolution audit, breadth/current-board counts | Data review; no inferred membership | ✅ Approved |
| **IX-4a** Index members endpoint + Universe filter | New read-only per-symbol index membership endpoint (reusing IX-3's exact resolution); Universe tab index filter | Owner review; no inferred mapping, no scoring/domain change | ✅ Approved |
| **IX-4b** Validation Workbench Results index filter | Index filter on the Workbench Results list, same membership data as IX-4a | Owner review; presentation-only | ✅ Approved |
| **IX-4c** Decisions index filter + selected-index view | Decisions index filter, selected-index Trade/Watch/No-trade view, ranking reuse, strict symbol handoff | Owner review; current-plan safety rules | ✅ Approved |
| **IX-5** Symbol Index Backdrop | Plain-language index alignment/divergence context in Decision Brief | Owner review; informational only | ✅ Approved |
| **IX-6** Evidence Review and Scoring Decision | Replay impact study and ADR proposal for any analytical influence | ADR + owner approval before code | ⏳ Planned |
| **IX-7** Relative-strength Symbol Index Backdrop | Magnitude-based outperform/lag reading for IX-5, reusing already-fetched data | Owner review; presentation-only, no new data/endpoint | ✅ Approved |
| **IX-8** Sector Leadership + Decision Breadth Combined View | Show decision breadth alongside the leading/lagging sector's price move, reusing already-fetched data | Owner review; presentation-only, no new data/endpoint | ✅ Approved |

**Implementation rule:** one IX milestone at a time. A market leader is not
automatically a trade, and a strong sector may not override an expired plan,
failed safety gate, weak symbol score, or unavailable data. IX-4 is split into
IX-4a/IX-4b/IX-4c (owner-approved 2026-08-01, design in
`docs/design/ATHENA-INDEX-SECTOR-INTELLIGENCE-ROADMAP.md`); each sub-milestone
gets its own owner-approval gate before the next starts.

#### IX-1 — tracked-index data foundation (approved, 2026-07-31)

Scope completed: added a validated twelve-index catalog covering NIFTY 50,
NIFTY BANK, NIFTY NEXT 50, NIFTY MIDCAP 100, and eight sector indices. The
Kite provider loads quote-only snapshot coverage from that separate catalog
while preserving the existing strict `kite.json` benchmark-history contract.
Market snapshots quote the larger display set together, while scoped symbol
validation continues to ingest historical candles only for the existing
benchmark pair plus VIX.

Added `GET /api/v1/market/index-intelligence`, a read-only response ordered by
configuration. Each row reports stable identity, family, persisted level,
prior-session change only when a real daily baseline exists, and explicit
`AVAILABLE` / `NO_DATA` state. The response exposes its persisted-snapshot
source and observation time. Missing index quotes remain isolated; they do not
erase available peers or become fabricated zeroes.

Rate-limit note: IX-1 adds the display indices to the existing bounded snapshot
quote request. It does not add those indices to per-symbol daily/5m/15m
historical ingestion. IX-2 must consume the persisted API and must not poll Kite
directly.

Architecture note: IX-1 is additive provider configuration and a read-only API
over the existing `MarketSnapshot`/candle ledger. `MarketSnapshot`,
`MarketDataProvider`, persistence schema, scoring, confidence, risk, decision
policy, TradePlan, and broker behavior are unchanged. No ADR is required.

Validation note: focused Kite provider and market-history/API tests pass
(37 tests). The full suite passes (1,132 tests); its only initial failure was
an older chart release-gate assertion pinned to asset version `9.89.0`, which
was aligned with the already-current `9.122.0` dashboard assets without
changing chart behavior.

Owner-QA correction: an initial IX-1 draft added
`snapshot_index_instruments` to strict `kite.json`. An already-running server
using the previous strict model rejected the new key during re-validation.
That same failure forced selected-symbol quote loading onto persisted data,
where day-change percentage is intentionally unavailable. IX-1 now leaves
`kite.json` unchanged and loads snapshot coverage from
`index_intelligence.json`; focused regression coverage verifies production
config compatibility and live snapshot resolution.

#### IX-2 — index leadership surface (approved, 2026-07-31)

Scope completed: added a compact Index Leadership ribbon inside Market
Summary, backed only by the persisted IX-1 index-intelligence endpoint. The
ribbon reports tracked-data coverage, broad-market movement, and sector
leadership/laggard context when trustworthy changes exist. A dedicated modal
shows all four broad-market and eight sector indices in deterministic groups
with level, change, observation time, and explicit unavailable states.

Session wording comes from the existing Calendar Engine session endpoint.
Market-open state is not inferred from Kite connectivity, and closed-session
copy includes the next live-session guidance supplied by that service. Missing
prior-session baselines render as `Change unavailable`; they never become
`0.00%`. Daily candles remain the preferred comparison source. Quote-only
display indices without daily candles use the latest persisted snapshot before
the current trading day, so no extra Kite history request is required. On the
first rollout day, those indices remain honestly unavailable until a real
prior-session snapshot exists. A single comparable sector is labeled `Sector
observed` instead of being misrepresented as both leader and laggard.

Refresh and layout notes: persisted index observations refresh with the
existing 60-second Market-tab ticker cycle, only while Market Intelligence is
active. IX-2 never polls Kite directly. Container-aware compact layouts keep
the ribbon within the narrower Market Summary column, while the grouped modal
uses a responsive one-column layout on narrow screens and has no horizontal
scroll.

Architecture note: IX-2 is frontend presentation/orchestration over
`GET /api/v1/market/index-intelligence` and
`GET /api/v1/dashboard/session-status`. It changes no provider protocol,
historical ingestion, persistence schema, scoring, confidence, risk,
decision policy, TradePlan, frozen domain object, or broker behavior. Index
movement remains explicitly labeled as market context, not an ATHENA trade
signal. No ADR is required.

Validation note: focused market-history/dashboard/release-gate tests pass (28
tests), and the full suite passes (1,133 tests). Browser QA with persisted data verified the
compact desktop ribbon, grouped desktop modal, narrow-screen modal, modal
open/close behavior, zero horizontal overflow in supported layouts, and no
browser console errors. MyPy reports no issues. Ruff reports only seven
pre-existing findings in the hosting regression file; IX-2 adds no new Ruff
finding.

Owner-QA correction: the dashboard assets can update without restarting an
already-running API process, so the new ribbon may initially call an IX-1
route that the old process has not registered. That failure previously looked
like a legitimate empty catalog (`0 of 0`) and also hid a successful market
session response. IX-2 now loads the index and session endpoints independently,
labels index request failures as `Index data unavailable`, preserves valid
session wording, and offers a retry action. A live localhost check against the
current code/config returned all 12 configured index levels after the restarted
ingestion process persisted its next snapshot. NIFTY 50 and NIFTY BANK also had
real prior-close changes; the remaining ten correctly showed `Change
unavailable` because IX-1 was deployed during the current session and no older
snapshot baseline existed yet. Regression coverage verifies that the next
session uses the prior-session snapshot and never a same-day observation.

Owner approval: IX-2 was approved on 2026-07-31 before IX-3 implementation
began.

#### IX-3 — versioned constituents and index breadth (approved, 2026-07-31)

Scope completed: added an immutable 2026-07-31 constituent snapshot for all
twelve configured broad-market and sector indices. Each source file is the
official NSE CSV captured from its archive URL. The colocated manifest records
provider, retrieval time, effective date, member count, source URL, SHA-256
checksum, and the explicit overlap policy. The loader rejects malformed
manifests, missing/unknown index keys, duplicate keys, path traversal,
checksum drift, CSV parse failures, and member-count drift.

Resolution is exact and fail-closed. A constituent symbol resolves only when
there is exactly one active NSE EQ instrument with that symbol. ATHENA does not
guess from company names, sectors, aliases, or partial matches. Every index
reports total, resolved, and unresolved membership plus snapshot age and
official source provenance. Symbols appearing in multiple indices are counted
once inside each index and independently across indices, matching the manifest
policy.

Breadth is read-only current-board composition, not market-price breadth and
not a trading signal. ATHENA selects exactly one latest persisted decision per
instrument using timestamp and decision-id tie-breaking. A Trade decision is
counted only while its TradePlan is current; Watch and No trade retain their
current-board categories. Trade, Watch, No trade, and Trade-breadth values are
published only when every constituent resolves and every resolved member has a
current board decision. Otherwise all breadth values remain unavailable and
the response identifies unresolved instruments or missing current decisions.

Presentation note: the existing Index Leadership detail modal now shows
membership date/age, resolution and decision coverage, composition when
complete, affected symbols when incomplete, and an official-source link. The
compact Market Summary ribbon remains leadership-focused and does not gain
high-density constituent detail. Responsive styling keeps the added context
inside the modal without horizontal scrolling.

Architecture note: IX-3 adds versioned source data, a strict data loader, one
deterministic read-only repository query, additive API fields, and dashboard
presentation. It changes no frozen domain object, persistence schema, provider
protocol, ingestion behavior, scoring, confidence, risk, decision policy,
TradePlan calculation, or broker boundary. No ADR is required.

Validation note: 43 focused constituent, repository, market-history,
dashboard-hosting, and chart release-gate tests pass. The full suite passes
(1,140 tests; one existing Starlette/httpx deprecation warning). JavaScript
syntax, final diff whitespace, and IX-3-owned Ruff checks pass; MyPy reports no
issues. Repository-wide Ruff still reports the pre-existing duplicate
`SizingConfig`, repository import/SIM findings, and older dashboard assertion
formatting findings. Owner-supplied desktop screenshots verify the 12-index
coverage ribbon, closed-session copy, complete NIFTY BANK breadth, fail-closed
incomplete peers with affected-symbol disclosure, official source links, and
no visible horizontal clipping. Authenticated automated browser interaction
remained blocked at Workstation Unlock; narrow-layout behavior remains covered
by dashboard regression assertions.

Owner approval: IX-3 was approved on 2026-07-31. The IX track is paused at the
owner's direction; IX-4 remains planned and must not begin until the owner
explicitly resumes and authorizes it.

#### IX-4a — index members endpoint + Universe filter (approved, 2026-08-01)

Owner resume/authorization: the owner explicitly resumed and authorized IX-4
on 2026-08-01. IX-4's combined scope was judged too large for one review
sitting and split into IX-4a/IX-4b/IX-4c (owner-approved 2026-08-01); design
detail in `docs/design/ATHENA-INDEX-SECTOR-INTELLIGENCE-ROADMAP.md`.

Design finding: IX-3's `_index_constituent_contexts` already resolves every
official constituent to at most one instrument and its current-board bucket,
but only serializes aggregate counts to the frontend — the per-symbol map is
computed and discarded. IX-4a serializes that same resolution via a new
read-only endpoint rather than building a second inferred mapping.

Scope completed: added `IndexMemberDTO`/`IndexMembersDTO`, a new
`MarketHistoryService.index_members()` reusing IX-3's exact resolution helper
(`_index_constituent_contexts` was refactored to derive its own aggregate
counts from the same per-symbol member list, so there is exactly one
resolution path, not two), and `GET
/market/index-intelligence/{index_key}/members` (404 via `IndexNotFoundError`
for an unknown/disabled key). The Universe tab now has an index-filter
dropdown mirroring the existing sector-filter pattern exactly: populated from
the already-fetched index-intelligence catalog, lazily fetching and
client-side caching each index's member list only on first selection,
disabling the control while that fetch is in flight, and surfacing the
unresolved-symbol count next to the filter rather than dropping it silently.
An index with `INCOMPLETE_INSTRUMENTS`/`INCOMPLETE_DECISIONS` still returns
its resolved members for filtering; only aggregate breadth stays suppressed.

Architectural note: IX-4a is a read-only endpoint over already-computed IX-3
resolution plus frontend presentation/filtering. It adds no broker write
action, no order placement, no scoring/confidence/risk/decision change, no
TradePlan value change, no provider protocol change, and no frozen domain
object change. Filtering is presentation-only over already-rendered Universe
rows; selecting an index never calls validation or mutates eligibility.

Validation note: 29 focused `TestIndexMembers`/`TestIndexIntelligence` tests
pass; full suite 1,147 passed; Ruff clean on all touched files (7 remaining
findings in `tests/api/platform/test_dashboard_hosting.py` are pre-existing,
confirmed via `git show HEAD` comparison, not introduced by this milestone);
MyPy reports no issues on touched source files. Live-verified in-browser
(DOM-bypass, matching the IX-3 precedent — no owner credentials available in
this environment): the toolbar renders search/status/sector/index filter on
one row without clipping, selecting an index calls the exact new endpoint
(`GET /market/index-intelligence/{key}/members`), and the 401-driven error
path correctly shows "Index membership unavailable." while re-enabling the
control rather than leaving it stuck disabled. Full authenticated interaction
with real membership data was not possible without owner credentials, same
limitation IX-3 recorded.

Owner approval: IX-4a was approved on 2026-08-01, committed as `3d19596`.

#### IX-4b — validation workbench results index filter (approved, 2026-08-01)

Owner authorization: the owner approved IX-4a and authorized starting IX-4b
on 2026-08-01.

Design: the Validation Pipeline Workbench's Results section
(`validationWorkbenchFilters()`, `validationResultRowView()`,
`compareValidationResultViews()`, `validationResultMatchesFilters()`,
`setValidationResultsBusy()` in `09-market-intelligence.js`) already reads
query/outcome/plan/sort filters and computes score/plan-freshness/outcome per
row — exactly the existing-fields ranking IX-4 requires. IX-4b adds one more
filter control of the same shape, reusing IX-4a's endpoint and client-side
membership cache rather than a second fetch/mapping.

Scope completed: extracted a shared `fetchIndexMembers(key)` helper so the
Universe filter (IX-4a) and this new Workbench Results index filter draw from
exactly one fetch/cache — never a second membership mapping. Added an "Index"
filter control to the Results toolbar (between Plan and Sort), a
`validation-results-index-filter-note` for unresolved-symbol counts, and
`filters.index` support in `validationWorkbenchFilters()`/
`validationResultMatchesFilters()` matching on the same bare-uppercase symbol
shape the Results rows already use. The new control participates in the
existing `setValidationResultsBusy()` disable/progress-feedback mechanism and
the existing Reset control, rather than introducing a second one.

Architectural note: IX-4b is frontend-only — no backend, DTO, or endpoint
changes (IX-4a's endpoint is reused as-is). It adds no broker write action,
no order placement, no scoring/confidence/risk/decision change, no TradePlan
value change. Filtering is presentation-only; selecting an index never calls
validation or mutates a result.

Validation note: full suite 1,147 passed; Ruff clean (same 7 pre-existing
`test_dashboard_hosting.py` findings, unrelated, confirmed via prior
IX-4a diff comparison — nothing new). No backend Python changed, so no
server restart was needed; confirmed the running server already served the
bumped cache-buster directly from disk. Live-verified in-browser (DOM-bypass,
same limitation as IX-3/IX-4a — no owner credentials available): opened the
Validation Pipeline Workbench, switched to the Results tab, confirmed the
Index filter renders between Plan and Sort with no clipping, and confirmed
selecting an index issues the identical IX-4a endpoint call and shows "Index
membership unavailable." on the expected 401 in this environment.

Owner approval: IX-4b was approved on 2026-08-01, committed as `d407260`.

#### IX-4c — Decisions index filter + selected-index view (approved, 2026-08-01)

Owner authorization: the owner approved IX-4b and authorized starting IX-4c
on 2026-08-01.

Design finding: `applyDecisionsView()` (`12-decisions-list.js`) already
filters `traceDecisionsList` down to `rows` by stance/type/query, sorts by
existing fields, and passes that same `rows` array to BOTH
`renderDecisionCarousels(rows)` (which already sections by TRADE/WATCH/
NO_TRADE and renders the summary strip) AND `topCurrentSetups(rows)` (TP-3's
existing score/confidence/risk/return/freshness ranking, reused verbatim).
This means IX-4c's "selected-index view of current Trade/Watch/No-trade" and
"rank only with existing fields" requirements are already satisfied by the
current architecture — adding one more membership predicate to `rows` (same
shape as the existing stance/type predicates) automatically scopes both the
carousels and the Top Current Setups queue to the selected index, with no new
view component or ranking algorithm needed. "Strict symbol handoff" is
likewise unchanged code (`preferInstrumentId`/`strictPreferInstrumentId`
already operate over whatever `rows` currently contains) — filtering by index
narrows `rows` the same way stance/type filters already do, so the handoff
mechanism itself needs no changes.

Scope: add a "Index" filter control to the Decisions filter popover (between
Type and Sort), reusing the exact same `fetchIndexMembers(key)` shared
cache/fetch introduced in IX-4b (no third membership mapping). The dashboard
JS files concatenate into one shared scope (confirmed: `12-decisions-list.js`
already calls `decisionScoreValue()` from `07-decision-format.js` verbatim),
so `09-market-intelligence.js`'s `fetchIndexMembers`/`universeIndexCatalog`
are directly reusable here without duplication.

Scope completed: added the "Index" filter control (with an unresolved-count
note), `populateDecisionsIndexFilter()`, `renderDecisionsIndexFilterNote()`,
and `applyDecisionsIndexFilterSelection()` to `12-decisions-list.js`, all
reusing IX-4a/b's `fetchIndexMembers`/`universeIndexMembersCache` verbatim —
zero new backend code, zero new fetch/cache implementation. Added one
membership predicate into `applyDecisionsView()`'s existing row filter
(alongside the pre-existing stance/type predicates), matching each row's bare
uppercase `instrument_id` against the selected index's resolved-member set.
Because that same filtered `rows` array already feeds both
`renderDecisionCarousels()` (which already sections by TRADE/WATCH/NO_TRADE
and drives the summary strip) and `topCurrentSetups()` (TP-3's existing
score/confidence/risk/return/freshness ranking), the selected-index
Trade/Watch/No-trade view and existing-fields ranking requirements are
satisfied with no new view component or ranking algorithm. The existing
`preferInstrumentId`/`strictPreferInstrumentId` handoff logic is unchanged
code operating over whatever `rows` currently contains, so strict symbol
handoff is preserved by construction, the same way it already was for the
pre-existing stance/type filters.

Architectural note: IX-4c is frontend-only — no backend, DTO, or endpoint
changes (IX-4a's endpoint/cache is reused as-is for the third time). It adds
no broker write action, no order placement, no scoring/confidence/risk/
decision change, no TradePlan value change. Filtering is presentation-only;
selecting an index never calls validation, never mutates a decision or plan.

Validation note: full suite 1,147 passed; Ruff clean (same 7 pre-existing
`test_dashboard_hosting.py` findings, unrelated). No backend Python changed,
so no server restart was needed; confirmed the running server served the
bumped cache-buster directly from disk. Live-verified in-browser (DOM-bypass,
same limitation as IX-3/IX-4a/IX-4b — no owner credentials available):
opened the Decisions & Trace Filters popover, confirmed the Index control
renders between Type and Sort with no clipping, and confirmed selecting an
index issues the identical shared endpoint call and shows "Index membership
unavailable." on the expected 401 in this environment. Decisions themselves
could not load without auth, so the carousel/Top-Current-Setups filtering
behavior with real data was verified by code reading (single shared `rows`
array) rather than live pixel inspection — the same limitation recorded by
every prior IX milestone in this environment.

Owner approval: IX-4c was approved on 2026-08-01, committed as `f69e4b8`.
The IX-4 track (IX-4a/b/c) is complete.

#### IX-5 — symbol index backdrop (approved, 2026-08-01)

Owner authorization: the owner approved IX-4c and authorized starting IX-5
on 2026-08-01.

Design: reuses `index_intelligence()`'s already-computed
`IndexIntelligenceItemDTO` items wholesale — no new per-symbol resolution
logic. The new backend method filters that same list down to the indices
whose official CSV membership (`membership.by_key()[key].symbols`, IX-3's
exact loaded data) contains the queried symbol; the returned items are the
identical objects `index_intelligence()` already returns, unchanged. On the
frontend, each membership item is rendered with the EXISTING
`indexObservationMarkup(item)`/`indexConstituentContextMarkup(item.constituents)`
functions (from IX-2, `09-market-intelligence.js`) — no new level/change/
breadth rendering code, since the item shape is identical to what those
functions already consume.

"Aligned vs diverging" is a plain sign comparison between the stock's own
`change_pct` (already live-polled into `activeBriefQuote`, DT-2/AW-1) and
each membership's `change_pct` — no magnitude threshold, no new numeric
constant, never fabricated when either side is unavailable.

Placement: a new section in the Decision Brief's existing "Market Context"
tab (`13-decision-brief-core.js`, alongside "Session & market context" and
"Data sources"), which the owner confirmed (via prior tab design) is the
correct home for supporting context — never the actionable Trade Plan tab.

Scope: new `GET /market/instruments/{instrument_id}/index-backdrop`
endpoint; `SymbolIndexBackdropDTO` (reusing `IndexIntelligenceItemDTO`
verbatim for `memberships`); `loadIndexBackdrop()`/`renderIndexBackdrop()` in
`15-decision-brief-context.js`, called alongside the existing
`loadDecisionContext()` call in `renderDecisionBrief()`.

Scope completed as designed: `MarketHistoryService.symbol_index_backdrop()`
and `GET /market/instruments/{instrument_id}/index-backdrop`; a new "Index
backdrop" section between "Session & market context" and "Data sources" in
the Market Context tab; `indexBackdropAlignment()` (plain sign comparison of
the stock's already-live-polled `change_pct` vs. each membership's, no
magnitude threshold); each membership row renders via the existing
`indexObservationMarkup(item)`/`indexConstituentContextMarkup()` (IX-2)
unchanged, and the alignment label via the existing `contextChip()` helper —
zero new rendering primitives. Honest-absence handling matches the existing
`context-caption`/`context-caption.unknown` convention (empty membership vs.
fetch failure are rendered distinctly, never conflated).

Architectural note: IX-5 is presentation-only. It adds one new read-only
endpoint (`Permission.READ`, same as every other market endpoint) and no
scoring/confidence/risk/decision/TradePlan change. `memberships` is never
consumed by any analytical engine.

Validation note: 5 new focused `TestSymbolIndexBackdrop` tests pass (34 total
in `test_market_history.py`); full suite 1,152 passed; Ruff clean on every
touched file (same 7 pre-existing `test_dashboard_hosting.py` findings,
unrelated). MyPy is not installed in this environment (no project venv, no
global install) and could not be run this round — noted honestly rather than
claimed. Restarted the server (backend changed this round) and confirmed the
new endpoint is registered correctly (`401` for an unauthenticated request,
not `404`/`500`). Directly verified `symbol_index_backdrop()` against the
real production `db/athena.db`/`config/` (bypassing the API auth layer, the
same diagnostic pattern used earlier in this project): INFY/TCS → `nifty_50,
nifty_it`; RELIANCE → `nifty_50, nifty_energy`; SBIN → `nifty_50,
nifty_bank, nifty_psu_bank` — all matching real NSE index composition, with
real level/change_pct/breadth values attached to each membership, including
an honest `INCOMPLETE_INSTRUMENTS`/`INCOMPLETE_DECISIONS` breadth status
where genuinely incomplete. Live-verified in-browser (DOM-bypass, same
limitation as every prior IX milestone — no owner credentials available):
no new console errors beyond expected 401 auth-noise. The populated section
itself could not be visually inspected because Decisions could not load
without auth in this environment, and the module-scoped render/load
functions are not reachable from a separate browser-console execution
context to synthesize a decision — the dashboard-hosting regression tests
and the direct production-data check above are the substitute evidence.

Owner approval: IX-5 was approved on 2026-08-01, committed as `55cfa03`.

#### IX-6 — feasibility check (2026-08-01): not started, owner deferred

Owner asked to start IX-6. Before writing any ADR or replay code, checked
`db/athena.db` directly for whether a statistically meaningful replay study
is currently possible, since IX-6 requires measuring stability, coverage,
false-positive reduction, and regime dependence:

- `decisions`: 4,413 rows, but all from a single trading day (2026-07-31
  09:26–15:30 IST) — one session, not a multi-week/month history.
- `market_snapshots`: 328 rows spanning 2026-07-24→07-31, but IX-1 (which
  added the 8 sector indices) only shipped 2026-07-31 — sector-index history
  barely predates the tracking itself. Only NIFTY 50/BANK NIFTY/VIX have any
  real pre-existing history.
- `trade_outcomes`: **zero rows.** No realized P&L/outcome data exists
  anywhere in the system yet.

A "false-positive reduction" or "before/after decision-band movement"
measurement is not statistically meaningful against one day of decisions and
zero recorded outcomes. Presented this finding to the owner with three
options (write a defer-ADR now documenting the gap; wait for more data; or
run a thin/dry-run study labeled inconclusive). **Owner chose to wait** —
IX-6 remains not started. No ADR was written, no replay code was added, no
scoring/analytical-influence work occurred. Re-check `db/athena.db`'s
`decisions`/`trade_outcomes` row counts and date range before resuming IX-6
in a future session; this finding does not need to be manually re-verified
if those counts have clearly grown to cover a real multi-week trading history
with recorded outcomes.

### Fix pass: 6 owner-reported dashboard UX issues (2026-08-01)

Owner reviewed live screenshots and reported six issues, unrelated to the IX
track, spanning Market Intelligence and Decisions & Trace:

1. **Index Leadership popup** — 2-column tile grid too sparse; changed to
   3 columns (`.index-leadership-grid`, `06-market-intelligence.css`).
2. **Universe and Validation Workbench Results toolbars wrapped to two
   lines** — IX-4a/b additions pushed both fixed-column-grid toolbars past
   capacity. Redesigned both to mirror Decisions & Trace's existing "Filters"
   popover pattern exactly (`#symbols-filter-toggle`/`-popover`): search and
   the primary action/count stay always-visible in one flex row; Status/
   Sector/Index (Universe) and Outcome/Plan/Index/Sort (Workbench) move
   behind one icon button. Reused `.symbols-filter-popover`/`.decisions-
   filter-label`/`.symbols-filter-reset-btn`/`.symbols-filter-close-btn`
   verbatim — no new popover CSS invented.
3. **Search bars had no clear (X) button** — added one to Universe's
   `#candidate-search-input` and Workbench's `#universe-search`, mirroring
   Decisions' existing `#briefing-search-clear` pattern exactly.
4. **Decisions & Trace Index filter stayed silently empty** until the owner
   happened to visit Market Intelligence first, with no indication why.
   Added `ensureIndexFilterCatalogLoaded()` — an idempotent, standalone fetch
   of the same index catalog, now also triggered the moment the Decisions
   tab itself loads, so the filter self-populates regardless of tab visit
   order.
5. **Filter/sort toggle gave no active-state indication.** Added a
   `.has-active-filters` modifier (highlighted border + small dot) to all
   three surfaces sharing the popover pattern (Decisions, Universe,
   Workbench), driven by each surface's own existing filter-read logic —
   no new state tracking invented.
6. **"Open decision" from a popup had a 2-3s unindicated delay** (tab switch
   + a genuine paginated decisions fetch) during which the owner could click
   elsewhere mid-navigation. Added a second, distinct blocking overlay
   (`#decision-open-overlay`, reusing the existing `validate-overlay` visual
   language, never repurposing it — its wording is specifically about
   re-validating) shown for the duration of `openDecisionForSymbol()`,
   guaranteed to clear via `try`/`finally` even on error.

**Two additional bugs found and fixed during this pass's own verification**
(neither owner-reported; both discovered live-testing item 2's popover):

- The Workbench Results popover's backdrop element sat inside the same small
  toolbar row as its own toggle button, shadowing clicks meant for the
  toggle (confirmed via `document.elementFromPoint`) while achieving no
  actual dimming effect (unlike Decisions' backdrop, scoped to the whole
  symbol list). Removed the non-functional backdrops from Universe and
  Workbench; the existing document-level click-outside listener already
  closes the popover without one.
- The Workbench Results modal's container carries a CSS `transform`
  (`matrix(1,0,0,1,0,0)`, functionally a no-op, but per the CSS spec ANY
  transform value creates a new containing block for `position: fixed`
  descendants). The popover there is now positioned relative to that actual
  containing block (computed at open-time), not the true viewport, with a
  purely geometric above/below flip and a `max-height`/`overflow-y` safety
  net shared by all three popover instances — never measuring the popover's
  own still-hidden (zero-height) box to decide.

Architectural note: presentation-only across all six items. No backend,
DTO, endpoint, scoring, confidence, risk, decision, or TradePlan change.

Validation note: full suite 1,152 passed; Ruff clean on every touched file
(same 7 pre-existing `test_dashboard_hosting.py` findings, unrelated). No
backend Python changed, so no server restart was needed. Live-verified in
the browser: Index Leadership grid confirmed 3-column via injected tiles
(real data unavailable without owner credentials, the same limitation every
IX milestone recorded); Universe toolbar/popover/search-clear/active-state
all confirmed correctly via screenshot; Decisions Index-filter catalog fetch
confirmed firing immediately on first Decisions-tab visit with no prior
Market Intelligence visit (network request observed); the "Opening decision"
overlay confirmed rendering correctly. The Workbench Results popover's exact
on-screen position could not be cleanly re-confirmed after the transform fix
within this session — every attempt coincided with `window.innerHeight`/
`getBoundingClientRect()` reading transiently corrupted values specifically
during synthetic (JS-dispatched) clicks in this browser-automation tool, a
reproducible artifact distinct from real user interaction (real mouse clicks
against real coordinates hit the correct element once measured correctly;
the corruption only affected geometry queries taken in the same tick as a
programmatic `.click()`). The underlying fix (containing-block-relative
positioning, verified by direct `getComputedStyle`/`elementFromPoint`
inspection) is logically sound and the same mechanism already renders
correctly for Universe's non-modal popover; re-verify this one surface
specifically on next touch if the owner reports it still misplaced.

#### Follow-up round (2026-08-01): 3 more issues from a second screenshot review

The owner reviewed the fix pass above live and reported three more issues:

1. **Workbench Results toolbar didn't match Universe's one-row design.**
   The search bar was still a separate row above the icon/count row (an
   artifact of the original markup, not fully folded into the popover
   redesign). Moved `.search-bar-container` to be the toolbar's own first
   child, matching Universe exactly: search grows via `flex: 1 1 auto`,
   count/busy pinned right via `margin-left: auto`.
2. **Index Leadership: 4 columns instead of 3, and a wider modal** (the
   owner's screenshot showed clearly unused screen width). Bumped the grid
   to `repeat(4, minmax(0, 1fr))` and the modal to `min(1320px, calc(100vw -
   32px))`.
   - **Bug found while verifying #2, predating this session:** the width
     override for `.index-leadership-modal-container` had been silently
     ineffective all along. `dashboard.css` `@import`s `06-market-
     intelligence.css` (where this override lived) BEFORE `07-universe-
     modals.css` (which defines the base `.modal-container { max-width:
     600px }` rule it needed to beat). Equal selector specificity means
     source order alone decides, so the later-loading base rule always won,
     regardless of the override's more specific-sounding class name — the
     modal has likely rendered capped at ~600px since this control was
     first built. Moved the override into `07-universe-modals.css`, right
     after the base rule, matching the exact pattern every other modal in
     this codebase already uses correctly (e.g.
     `.validation-funnel-modal-container`, defined in that same file).
3. **Validating/re-validating a symbol and opening a decision took
   15-20 seconds.** Root cause: `fetchAllDecisionPages()` fetched the
   decisions collection one sequential round-trip per 100-row page — with
   the table now in the thousands, 40+ awaited requests in series. Worse,
   `validateSymbolsNow()`'s `refreshDecisions` path called BOTH
   `loadMarketIntelligence()` (which already refreshes the same shared
   decisions cache via `refreshDecisionCacheForValidationResults()`) AND
   `loadDecisionsWorkspace()` (which fetched the entire collection a SECOND
   time). Fixed both: `fetchAllDecisionPages()` now fetches page 1 to learn
   the real page count, then fires every remaining page concurrently
   (`Promise.all`) instead of one at a time — `page_size` stays at its
   server-enforced cap of 100 (`PaginationParams`, `le=100`), no backend
   contract change; and the redundant `loadDecisionsWorkspace()` call was
   replaced with `applyDecisionsView()` re-applied over the already-fresh
   cache, eliminating the duplicate fetch entirely.

**One more latent bug spotted in passing (not owner-reported, flagged as a
separate follow-up task, not fixed in this pass):** CSS served via
Starlette's `StaticFiles` mount carries no explicit `Cache-Control` header,
so browsers apply heuristic freshness independent of `index.html`'s own
cache-bust version bump — a `css/*.css` edit can be invisible to a returning
user's browser (unlike `dashboard.js`, which is server-concatenated into one
versioned URL) until they hard-refresh. Confirmed reproducible in this
session's own testing. Out of scope for this fix pass; flagged separately.

Architectural note: presentation-only. No backend, DTO, endpoint, scoring,
confidence, risk, decision, or TradePlan change. The `fetchAllDecisionPages`
change touches only client-side request fan-out, not the `GET /decisions`
contract itself.

Validation note: full suite 1,152 passed; Ruff clean (same 7 pre-existing
`test_dashboard_hosting.py` findings, unrelated); CSS/JS brace-balance
checked; no backend Python changed, so no server restart needed. Live-
verified in the browser: Workbench Results toolbar confirmed one row,
matching Universe, via an injected style override to bypass this session's
own stale-CSS-cache artifact (see above) in the specific test tab; Index
Leadership confirmed rendering 4 columns at the intended ~1248px width the
same way, once the override was applied — proving the underlying fix is
correct, with the caching gap (not this fix) responsible for the tab not
picking it up via a normal reload. The 15-20s performance claim itself could
not be directly timed in this environment (no representative decision-table
volume/latency to reproduce against), but the root cause (40+ serial
round-trips, doubled on every revalidate) was confirmed by direct code
tracing against the real `GET /api/v1/decisions` pagination contract, and
the fix's correctness (page 1 informs `total_pages`, remaining pages requested
concurrently, results reassembled by page order) was verified via full-suite
regression coverage and code review.

#### Third round (2026-08-01): the follow-up round's fixes were not actually working

The owner's next screenshots showed the Results tab and its Filters & Sort
popover both still broken, despite the follow-up round above claiming both
were "confirmed correct." Re-investigated from scratch instead of trusting
that claim:

1. **Results tab: "Showing 0" despite Conversion showing 363/510 eligible ·
   200 trade.** Confirmed via direct SQLite query against the live database:
   23 pipeline runs ran that day, every one FAILED. The Results tab's
   `GET /api/v1/pipelines/runs` fetch had no `page_size`, defaulting to 20 —
   it only ever saw that day's 23 failures. The Conversion/funnel stat comes
   from a separate backend endpoint (`validation_funnel()`) that explicitly
   requests `page_size=50`, reaching back far enough to find the last
   successful run (confirmed at rank #25 by recency, from the prior day).
   Fixed by requesting `page_size=100` (the API's max) with an explicit sort
   on the one frontend call site.
2. **Filters & Sort popover still rendering cut off.** The follow-up round's
   fix (re-basing `position: fixed` math against a transformed ancestor) was
   the wrong root cause. The real cause: `.modal-body`'s `overflow-y: auto`
   clips any descendant popover regardless of how correct its position math
   is — CSS clipping follows DOM containment, not the positioned element's
   containing block. Fixed with a real DOM portal: the popover detaches to
   `document.body` while open (its own `z-index: 2200`, since it's now a
   sibling of `.modal-overlay`'s stacking context, not a descendant of it),
   and restores to its original position on every close path (toggle
   re-click, close button, outside click, Escape, switching away from the
   Results tab, and all three paths that close the parent modal).
3. **Third screenshot review, once data started loading, found 3 more UI
   issues:** the search input's unbounded `flex: 1 1 auto` left too little
   separation from the toggle/count — capped at `max-width: 420px`; the
   viewport-clamped popover could still spill past the dialog card's own
   edge onto the backdrop when the modal is narrower than the viewport —
   reclamped against `.modal-container`'s own rect instead of the full
   viewport; and picking a filter/sort value left the popover open — each
   select now closes it after applying.
4. **Separately reported: the search box froze the UI while typing.**
   `latestDecisionForSymbol`/`currentOpenableDecisionForSymbol` each did a
   full `.find()` scan of `traceDecisionsList` (thousands of decisions) for
   every result row on every debounced render — O(rows × decisions) per
   keystroke. `traceDecisionsList` is already deduped to one decision per
   instrument, so replaced the scan with a `symbol → decision` `Map`,
   rebuilt once whenever `traceDecisionsList` itself is reassigned; both
   lookups are now O(1). Benchmarked at realistic scale (510 symbols, 4413
   decisions, via a standalone Node.js script reproducing the real algorithm
   shape): 12.03ms → 0.74ms per render, ~16x.

**Verification approach changed deliberately this round.** The prior round's
"confirmed correct" claim rested on checking computed CSS values in a test
tab, which never actually exercised the real clipping ancestor — a real
defect passed as verified. This round used a throwaway static page
(temporarily served from the existing `/dashboard` mount, deleted
immediately after) reproducing the real DOM structure — including the
scrollable modal body — loading the real `dashboard.css` and the exact
current JS functions, exercised via the actual browser with
`getBoundingClientRect()` diagnostics, not visual inspection alone. The
`page_size` root cause was confirmed directly against the live database, not
inferred. The lookup fix was benchmarked directly, not just asserted.

Architectural note: presentation-only; one frontend-only fetch parameter
change. No backend, DTO, endpoint, scoring, confidence, risk, decision, or
TradePlan change.

Validation note: full suite 1,152 passed. New assertions cover every item
above (portal helpers, modal-bounds clamp, auto-close-on-change wiring,
search bar max-width, the `traceDecisionsBySymbol` index and its two call
sites, and that neither lookup function contains `.find(` anymore).

---

### Intraday Edge Program (post M-D4, owner direction 2026-07-25)

AI-driven roadmap toward a "no compromise" world-class intraday analyzer.
AI proposes and implements; owner approves each completed milestone before
the next starts (per CLAUDE.md milestone workflow — unchanged). Every item
below was checked against ATHENA-002 §2/§4/§7/§19 and Risk Register R6
(module map closed, domain/contracts frozen, no scope creep) before being
added here — anything touching a frozen contract is ADR-gated; anything
needing a new external data source is DD-gated. Nothing on this list is
implemented silently past those gates.

| Milestone | Scope | Gate | Status |
|---|---|---|---|
| **M-X0** Decision Journal & Outcome capture | Wire the already-modeled `DecisionJournalEntry`/`TradeOutcome` (frozen domain, existing repository methods) to a real owner action: Accept/Reject/Ignore on the Decision Brief, realized-outcome logging with server-computed pnl/holding-time/TradePlan-adherence. Closes the gap where `save_journal_entry` was called nowhere in the codebase and M10.4 AI Playbook Diagnostics ran against an always-empty journal. Prerequisite for M-X1/M-X10. | None — existing frozen domain objects + repository methods, just unconnected | ✅ Approved |
| **M-X1** Historical analog matcher | Deterministic nearest-neighbor retrieval of past decisions with a similar score/confidence/risk fingerprint + their logged outcomes, surfaced in the Decision Brief | None — read-only query over existing persisted Decision Journal | ✅ Approved |
| **M-X2** "Why not" counterfactual | Quantify exact score/confidence gap between a WATCH and the TRADE gate | None | ✅ Approved |
| **M-X3** Confidence-decay clock | Persisted, deterministic decay indicator for TradePlan staleness through the session | None | ✅ Approved |
| **M-X4** Circuit-limit / price-band risk signal | New Risk Engine dimension from Kite's already-fetched, currently-discarded circuit-limit fields | **ADR-006 (Proposed)** — extends frozen `Quote` domain object | ⏸ Blocked on ADR approval |
| **M-X5** Opening Range Breakout playbook | First-15/30-min range break/hold as a deterministic strategy-framework pattern | None | ⏳ Planned |
| **M-X6** VWAP deviation scoring dimension | Intraday VWAP reclaim/deviation as a new scoring input | None | ✅ Approved (2026-08-02) |
| **M-X7** Multi-timeframe confluence | Daily/5m/15m trend-direction agreement as a scoring input (see design note: 1m and "confidence dimension" both reconsidered) | None | ✅ Approved (2026-08-02) |
| **M-X8** Synthetic canary decision | Fixed synthetic instrument through the full pipeline each cycle to catch silent engine regressions | None | ✅ Approved (2026-08-02) |
| **M-X9** Config-change impact preview | Deterministic replay-based diff of a scoring-weight change against recent decisions, before it goes live | None | ✅ Approved (2026-08-02) |
| **M-X10** Outcome-tagged setups + signal drift monitor | Extends M10.4 AI Playbook Diagnostics with per-pattern hit-rate tagging and weight-drift alerts (see design note: "pattern" scoped to regime trend label, data-gated on real outcomes) | None | ✅ Approved (2026-08-02) |

#### M-X6 — VWAP deviation scoring dimension (approved, 2026-08-02)

**Design confirmed before any code:** re-checked against ATHENA-002 before
implementing, since adding "a new scoring input" could easily have meant a
7th weight slot in the frozen 6-dimension `ScoringWeightsCfg` (an ADR-gated
change). It doesn't — `IndicatorName.VWAP`/`config/indicators.json`'s
`vwap` version entry/`EvidenceCategory.VWAP` were all already
pre-provisioned in the codebase awaiting exactly this milestone, and VWAP is
wired as an additional named `Contribution` inside the existing
`technical_structure` dimension, the same pattern already used for MACD's
bonus (which itself shipped inside M3.2 with no separate gate). No frozen
contract changed; confirmed `ScoringWeightsCfg`'s 6 dimensions and their
weights are byte-for-byte unchanged.

**A real, separate risk found during design and designed around from the
start:** VWAP is fundamentally a same-session (intraday) calculation, unlike
every other indicator here which reads the daily series. If VWAP had been
merged into the same `indicators` dict `ConfidenceEngine._indicator_availability`/
`_unknown_ratio` measure completeness over (`known/len(indicators)`), it
would silently move every symbol's confidence score whenever intraday
history happens to be thin (5m data is far sparser than daily) — the exact
un-reviewed-impact risk SD-2/SD-3 treat explicitly for `sector_quality`.
Fixed structurally, not by convention: `vwap` is its own parameter on
`ScoringEngine.score()`, exactly like `market_health_score`/`sector_health`
already are, never merged into `indicators`. Verified end-to-end against the
real production config (not a mock) that `indicator_availability` stays
locked at "6/6 OK" whether or not VWAP is available for a symbol.

Scope: `calc.vwap()` (`src/athena/indicators/calculations.py`) — session-
cumulative typical-price/volume, resets each calendar day; `IndicatorEngine._vwap`
+ `IndicatorName.VWAP` wiring (no exhaustive match statements existed to
update — dispatch is reflective via `getattr`); `TechnicalScoringCfg` gets
two additive fields (`vwap_deviation_cap_pct`, `vwap_max_bonus`) for an
SD-4-style anchor-preserving `_linear_ramp` bonus (0 at/below VWAP, up to
the max at the deviation cap — "VWAP reclaim" is this ramp becoming
positive, decided at the scoring layer, never inside the indicator itself,
matching how MACD's `histogram > 0` bonus decision already works);
`OwnerValidationPipeline` fetches same-day 5m candles per included
instrument and computes VWAP as a value separate from the daily `indicators`
dict, threaded through to `_technical_structure` alone.

**A real bug found and fixed during self-validation, not left for the
owner to discover:** the workflow engine validates each stage's declared
`produces` output keys against what it actually returns
(`src/athena/runtime/workflow.py`); adding the `"vwap"` key to `ind_stage`'s
return value without updating its `WorkflowStage(..., produces=("indicators",))`
declaration caused every single scan to fail silently as `WorkflowError`
(discovered via the full suite — 6 pre-existing owner_validation tests
failed). Fixed by updating the declaration to `("indicators", "vwap")`.

Validation note: full suite 1,177 passed (11 new: 5 indicator-level tests
including a mixed-day session-filtering case, 5 scoring-level tests
including the SD-4 anchor test and the explicit
indicators-dict-untouched regression test, 1 end-to-end pipeline test
proving the confidence isolation holds against the real config). Ruff
clean. Also verified against real historical data: computed VWAP for a real
equity (`NSE:RRKABEL`) from a real trading day's actual 5m candles in the
production database — result (₹2621.60) fell squarely inside that day's
real price range (₹2593–₹2660.6) and close to its average close (₹2623.28).

Architectural note: presentation/scoring-input only, additive to the
already-approved M3.2/M3.3 engine contracts. No provider, broker, order,
domain, or frozen-contract change. No ADR required per the design analysis
above.

**Explicitly not started — owner decision required, not an AI call:**

| Item | Why it's gated | Revisit point |
|---|---|---|
| ASM/GSM surveillance-stage awareness | New NSE data source; no existing DD covers it | Needs a new DD (owner decision on vendor/method) before any code |
| Delivery % (NSE daily delivery data) | New NSE data source | Needs a new DD |
| Bulk/block deal feed | New NSE data source | Needs a new DD |
| Options data + F&O ban-list feed | **DD-4** already exists in ATHENA-002 §15, deferred to "Phase 7" — Phase 7 is now approved, so DD-4 is revisit-eligible | Owner decision: open DD-4 now or keep deferred |

#### M-X7 — Multi-timeframe confluence (approved, 2026-08-02)

**Design confirmed before any code — the backlog's own wording didn't
survive contact with the real data or the frozen contracts:**

1. **"1m/5m/15m" scoped down to daily/5m/15m.** `IngestionConfig` and the
   domain/provider layers already support 1m structurally (no schema/ADR
   needed), but the live database has **zero 1m candle rows** — enabling it
   would take weeks to accumulate anything usable. Implementing against
   data that doesn't exist would be exactly the kind of fabricated-value
   risk ADR-005 forbids, so 1m is out of scope here, not deferred silently:
   it's named explicitly so a future milestone doesn't assume it was
   already handled.
2. **"scoring/confidence dimension" resolved to scoring only.** A new
   `ConfidenceEngine` dimension would mean editing the frozen, sum-to-100
   `ConfidenceWeightsCfg` + its validator + re-dividing every existing
   weight — the same class of ADR-adjacent change M-X6 avoided for
   `ScoringWeightsCfg`, and not actually "Gate: None" as the backlog
   claims. Implemented instead as an additional named `Contribution` inside
   the existing `trend` scoring dimension, mirroring the ADX-bonus pattern
   already there (and the VWAP-in-`technical_structure` pattern M-X6 just
   established) — no frozen contract touched, confirmed `ScoringWeightsCfg`'s
   6 dimensions and `ConfidenceWeightsCfg`'s 6 dimensions are both
   byte-for-byte unchanged.

**A real, separate data risk found during design and designed around from
the start:** real 15m history runs as thin as **9 bars/session**
(production DB check: 513 instruments, 15m min/avg/max = 9/14/73
bars/session) — too thin for a fixed n-of-3 agreement check. Confluence is
built UNKNOWN-tolerant by construction: bonus = (timeframes agreeing with
the daily direction) / (timeframes with enough history to even check) ×
`max_bonus`. A timeframe below its own short SMA's minimum history is
excluded from the ratio entirely, never counted as disagreement — a
thin/missing 15m series degrades gracefully to a 5m-only read instead of
dragging the bonus toward zero or going UNKNOWN.

Scope: `ConfluenceInputs` (`src/athena/scoring/models.py`) — a small,
purpose-built frozen dataclass (`daily_bullish`, `five_min_bullish`,
`fifteen_min_bullish`, with `checked`/`agreeing` properties), not a new
engine — the underlying computation (last close vs. a short trailing SMA)
doesn't warrant one. `ConfluenceScoringCfg` (`src/athena/config/models.py`)
adds `five_min_sma_period`/`fifteen_min_sma_period`/`max_bonus`, config-driven
like every other scoring threshold. `ScoringEngine._trend` gets the bonus as
a proportional `agreeing/checked × max_bonus` contribution (same SD-4
anchor-preserving shape as ADX/RSI/VWAP, reproducing 0/half/full bonus at
0/1/2 agreeing exactly). `OwnerValidationPipeline.ind_stage` reuses the same
5m series already fetched for VWAP (M-X6) and adds one new 15m fetch;
directions are computed with `calc.sma()` directly (not routed through
`IndicatorEngine`, since `IndicatorsConfig` fixes one period per indicator
name and 15m's real thinness needs a shorter period than the daily
series' SMA(20)). `confluence` is its own `score()` parameter, never merged
into `indicators` — identical isolation reasoning to VWAP's, since it's
also derived from same-session-sparse series.

**The exact silent-failure bug M-X6 hit was not repeated:** `ind_stage` now
returns a `"confluence"` key alongside `indicators`/`vwap`, and
`WorkflowStage(..., produces=(...))` was updated to
`("indicators", "vwap", "confluence")` in the same change — the workflow
engine validates a stage's declared `produces` against what it actually
returns and raises `WorkflowError` on any mismatch.

Validation note: full suite 1,186 passed (9 new: `ConfluenceInputs`
checked/agreeing unit tests, 5 `ScoringEngine._trend` confluence-bonus
tests including the SD-4 proportional-ramp anchor test and the
never-provided backward-compatibility test, 2 end-to-end
`OwnerValidationPipeline` tests against the real production config — one
proving `indicator_availability` stays "6/6 OK" regardless of confluence
availability, one proving a 15m series thinner than its own SMA period
still resolves ("1/1" from 5m alone) instead of erroring). Ruff clean.
Also verified with two real, full end-to-end `OwnerValidationPipeline` runs
against a working copy of the production database (real 2026-07-31 candle
history; the copy was used specifically so the runs would never write a
decision into the live decisions table) — owner-requested, beyond the
suite above:

- **`NSE:RRKABEL`**: real run produced an actual `TRADE` decision; trend
  contributions showed no `confluence:intraday` entry. To rule out
  confluence silently not running (a zero bonus and "never computed" are
  indistinguishable from the contribution list alone), the actual
  `ConfluenceInputs` constructed inside that live call was captured via
  instrumentation — confirmed `checked=2, agreeing=0` (daily bullish, both
  5m and 15m bearish): confluence *did* run, and correctly contributed
  nothing for a genuine short-term pullback rather than fabricating a
  tie-break.
- **`NSE:360ONE`**: scanned real candidates for one with genuine 2/2
  agreement at the same as-of, then ran it through the same real pipeline —
  produced `confluence:intraday: "2/2 intraday timeframe(s) agree with
  daily direction → +10.00 pts"`, trend 90. Confirms the bonus path renders
  correctly end-to-end on real data, not only in synthetic tests.

Architectural note: presentation/scoring-input only, additive to the
already-approved M3.3 engine contract. No provider, broker, order, domain,
or frozen-contract change. No ADR required per the design analysis above.

#### M-X8 — Synthetic canary decision (approved, 2026-08-02)

**Design confirmed before any code — the backlog's own "Gate: None" claim
was checked, not assumed, exactly as for M-X6/M-X7:** the real risk found
was that `Decision` (`src/athena/domain/decision.py`) has no
source/kind/synthetic field, and nothing in `save_decision`/`list_decisions`/
the API router filters by one — **any persisted decision shows up
unconditionally in the real dashboard, Decision Brief, and Journal.** A
naive "flag it as synthetic" implementation would mean adding a field to
the frozen domain model (ADR-gated per ATHENA-002 §4/§19), the same class
of near-miss M-X6 hit with `ScoringWeightsCfg` and M-X7 hit with
`ConfidenceWeightsCfg`. Avoided structurally instead: the canary never
calls `save_decision` at all, and never touches the real repository —
it runs the real, unmodified `OwnerValidationPipeline` against a fresh,
throwaway **in-memory** `SqliteRepository` created for that one call and
discarded immediately after. Confirmed no existing "canary"/"synthetic
regression" concept existed anywhere in the repo before this (the closest
precedent is T-3's dormant golden-dataset regression test skeleton,
`tests/golden/README.md`, never populated — a design-time, not live,
mechanism).

**Owner decision on placement:** embedded directly in the live scheduler
(`HostDueRunner.run()`, `src/athena/ops/scheduled_run.py`) rather than a
standalone CLI command, so it runs automatically after every real
PREMARKET/REFRESH/CLOSING cycle the host cron fires — the fullest "catch
regressions automatically, unattended" reading of "each cycle." Runs once
per host tick (alongside whichever real triggers fired that tick), not once
per trigger.

Scope: `src/athena/ops/canary.py` — a fixed, deterministic, steadily-rising
80-bar daily-only synthetic instrument (`NSE:ATHENACANARY`, never a real
listed symbol), reusing the same shape as `tests/decision/test_scoring.py`'s
own `_candles()` fixture pattern but as a production diagnostic input, never
shown to the owner as real market data. `run_canary()` seeds a brand-new
in-memory repo with exactly this one synthetic candidate/instrument/candle
set and runs the real `OwnerValidationPipeline.run()` against it unmodified
— reusing the exact code path real trading decisions go through (including
M-X6's VWAP and M-X7's confluence wiring) rather than a parallel,
simplified re-implementation that could itself silently drift out of sync
with the real pipeline. "Regression" is deliberately loose, not an exact
expected decision: concentration risk on a single-instrument universe is a
real, legitimate `RiskEngine` outcome, not a bug, so an exact `TRADE`
expectation would be brittle. Instead it checks the pipeline completes
without raising and returns a fully-explained (status OK) score/confidence/
risk for an input that always has complete daily history by construction,
plus a recognized `decision_type` (flagging `INSUFFICIENT_DATA` specifically,
since that's impossible for this always-complete synthetic input if the
pipeline is working correctly).

Wired into `HostDueRunner._run_canary()`: runs after the real due-trigger
cycles complete, wrapped so **any** exception — from the canary's own code,
not just a detected regression — is caught and never propagates, since a
diagnostic breaking must never take down the real scheduled cycle it's
checking alongside. On a detected regression (or the canary itself
erroring), alerts through the existing DD-9 `FailureAlertDispatcher` path
with `source="canary"` — the same file/webhook channels `run-due` hard
failures already use, zero new alerting mechanism. Added an additive
`canary: CanaryResult | None = None` field to `HostDueRunResult` (an ops
dataclass, not part of the frozen domain model — no gate) so the outcome is
directly testable/observable, not just a side-effect. `None` means "didn't
run this tick" (no `config_dir` wired — matches `_is_trading_day`'s own
backward-compatible fallback for pre-existing callers); only
`CanaryResult(ok=True, ...)` means it ran and passed.

Validation note: full suite 1,198 passed (12 new: 5 `run_canary()` tests
against the real production config — including a determinism-repeat check
and a broken-config-dir case proving a `load_config` failure is reported as
a regression, not left to crash the caller — plus 2 `CanaryResult`
construction tests; 5 `HostDueRunner` integration tests proving the canary
actually runs when `config_dir` is wired (against real production config,
not a mock), is skipped (not a new failure mode) when it isn't, never
propagates its own exception into a real cycle, alerts with `source="canary"`
on a detected regression, and stays silent on a pass). Ruff clean.

Architectural note: ops/diagnostics-only, additive. No provider, broker,
order, domain, or frozen-contract change — confirmed by design analysis
above, not assumed. No ADR required.

#### M-X9 — Config-change impact preview (approved, 2026-08-02)

**Design confirmed before any code, including tracing a suspicious
precedent rather than trusting it:** SD-2's own entry references "the
existing D-3 impact table" and a "60.1%" figure as if a replay tool already
existed. Traced it: D-3 (`docs/MILESTONES.md`) is a root-cause table, not a
mechanism, and the 60.1% figure came from a one-off, uncommitted, prose-only
calculation — `grep`ing the repo for any script reproducing it returns
nothing, and `IMPLEMENTATION_SUMMARY.md`'s own SD-1 entry notes an earlier
version of that same manual "simulator" was "discarded as unsound." M-X9
had no working precedent to build on; it had to be built from scratch.

**The research's own first recommendation (reconstruct typed engine inputs
from the persisted `decision_reports` JSON) was checked against the actual
serializer and found non-viable, not just complex:** `DecisionReportingEngine._indicators()`
(`src/athena/reporting/engine.py`) only persists `name`/`status`/`values` —
it discards `IndicatorResult.evidence` entirely, and `ScoringEngine._technical_structure`
needs `evidence.inputs["last_close"]` to determine price-vs-SMA. Replaying
from the persisted JSON would silently degrade `technical_structure` to
UNKNOWN for every replayed decision — a worse, less-faithful preview than
the real thing, not a shortcut.

**Design used instead — mirrors M-X8's canary pattern exactly:** for each
of the `limit` most recent real decisions (`repo.list_decisions`), fetch
that instrument's real daily candles bounded strictly at-or-before the
decision's own `ts` (`repo.get_candles(..., end=decision.ts)` — no
look-ahead) and the real historical market snapshot in effect at that time
(`repo.get_latest_snapshot_before(decision.ts)`), seed a fresh throwaway
in-memory repo with exactly those, and run the real, unmodified
`OwnerValidationPipeline` against it — once under the current config, once
under the candidate config. Fully faithful (real historical data, not a
reconstruction), zero new deserialization code, zero new persisted schema.
`repo` (the real one) is only ever read (`list_decisions`/`get_instrument`/
`get_candles`/`get_latest_snapshot_before`) — never written.

**A real, separate methodology risk found via real-data validation, not
assumed correct on paper:** running this against the live production
database (read-only — the module never writes, confirmed safe to test
directly) revealed that `original_decision_type` (the real, full-universe
decision) frequently differs from `current`'s replayed type even under the
*identical* config. Root cause: each replay is scoped to one instrument
(`symbols_filter`), so `RiskEngine`'s concentration read sees a
single-instrument universe with no prior-run history — a materially
different context than the original multi-instrument scan. This is a
replay-methodology artifact, not a bug, and not what this tool compares:
`current` vs `candidate` are both computed under the identical
single-instrument context, so the concentration effect is held constant on
both sides and only the config difference can move the result. Documented
explicitly in the module docstring and printed as a footnote in the CLI
output, rather than left for the owner to notice and worry about.

Scope: `src/athena/ops/config_preview.py` (`replay_decision_under_config`,
`preview_config_change`, `ConfigPreviewReport`) — none of it persisted, all
transient/computed-on-demand. New CLI command `athena config-preview
<candidate_config_dir> [--limit N]` (`src/athena/cli.py`), matching the
CLI-only-first-cut precedent DD-12's `athena backfill-sector-indices`
already established, per ADR-004 (no dashboard surface needed for v1).

Validation note: full suite 1,209 passed (11 new: 7 `replay_decision_under_config`/
`preview_config_change` tests including a determinism check, a real
candidate-weight-edit test proving the mechanism detects an actual change,
and two never-writes-to-the-real-repo regression tests; 2 skip/empty-report
edge cases; 2 CLI-level tests). Ruff clean. Also verified directly against
the real production `config/`/`db/athena.db` (read-only — the module has
no write path to the real repo, confirmed safe): replaying the 15 most
recent real decisions under an unchanged candidate config reproduced 0
changes (confirming determinism); replaying under a genuinely different
candidate (all scoring weight onto `liquidity`) correctly flagged 2/15 as
changed (`TDPOWERSYS`/`RELIANCE`: `WATCH → NO_TRADE`).

Architectural note: ops/diagnostics-only, additive. No provider, broker,
order, domain, or frozen-contract change. No new persisted schema — the
report is transient. No ADR required per the design analysis above.

#### M-X10 — Outcome-tagged setups + signal drift monitor (approved, 2026-08-02)

**Design confirmed before any code, and reconsidered twice mid-design as
new facts surfaced — the backlog's premise turned out to be materially
incomplete, not just under-specified:**

1. **Checked whether M-X0 (Decision Journal & Outcome capture, already
   approved) actually has data to tag.** It doesn't: the live production
   database has **zero rows** in `decision_journal` and `trade_outcomes` —
   the Accept/Reject/Ignore + outcome-logging UI shipped and was tested,
   but hasn't been used since. Confirmed with the owner directly rather
   than assumed: build the plumbing now, data-gated, so hit-rate output
   appears naturally once real outcomes accumulate rather than deferring
   the whole milestone or building it un-gated against data that doesn't exist.
2. **Checked whether "per-pattern" tagging could reuse an already-computed
   `StrategyMatch` (momentum/breakout/mean_reversion/etc.) — it can't.**
   `StrategyFramework`/`ScheduleEngine` are fully built and tested but
   **never instantiated anywhere in the real live pipeline**
   (`HostDueRunner`/`OwnerValidationPipeline`) — a dormant, orphaned
   subsystem from an earlier phase, not a "just persist what's already
   computed" situation. Wiring the entire scanner→watchlist→strategy→
   analytics chain into live production would be its own milestone-sized
   effort, well beyond "extends M10.4." Confirmed with the owner again:
   scope "pattern" to the regime trend label (BULL_TREND/SIDEWAYS/
   BEAR_TREND) instead — already computed and persisted for every real
   decision today, zero new subsystem wiring, zero new persistence table.

**Gate: None held, but only because of these two corrections** — a naive
literal reading of the backlog line would have either required wiring a
dormant subsystem into live production or shipped inert code against data
that will never arrive without the owner using the journal UI.

Scope, in three additive pieces:

1. **`outcome_source` actually wired.** `_cmd_diagnose` had *always*
   constructed `PlaybookDiagnosticsService` with no `outcome_source` —
   `athena diagnose` has only ever seen ops/run data in production, never
   a real decision or journal entry, despite the M10.4 analyzer supporting
   both since it shipped. New `RepositoryOutcomeSource` (bounds
   `list_decisions`/`list_journal` to `ts <= as_of`, no look-ahead) closes
   that gap. New `DiagnosticsConfig.lookback_decisions` (separate from
   `lookback_runs` — decisions accumulate far faster than run records).
2. **Per-pattern hit-rate tagging.** `PlaybookDiagnosticsAnalyzer.analyze()`
   gets two new optional parameters (`trade_outcomes`, `pattern_labels`),
   backward compatible with every existing caller. Regime trend label per
   `decision_ref` is resolved by the service layer from the persisted run
   detail (`decision_reports` → `regime.evidence` where
   `dimension == "trend"` — the exact same source `ScoringEngine._trend`
   itself reads its own label from), never re-derived or guessed. Each
   pattern bucket is reported only once it independently reaches
   `min_sample_size` outcomes — an under-sampled bucket is silently
   omitted, not a misleadingly precise statistic, matching
   `_adherence_proposals`'s existing `blocked`-gating philosophy.
3. **Signal drift monitor.** New `src/athena/diagnostics/weight_drift.py` —
   `WeightSnapshot` (scoring weights + `min_composite_for_trade`), captured
   to a plain JSON file under `DiagnosticsConfig.output_dir` (mirroring
   `FailureAlertDispatcher`'s own artifact-file pattern — no new DB table,
   no new schema). New `athena weight-drift-baseline` CLI command captures
   it; `athena diagnose` compares the current config against it every run
   and, on any drift, both emits a `DiagnosticFinding` (visible in the
   report) and dispatches an alert through the existing DD-9
   `FailureAlertDispatcher` (`source="weight-drift"`) — zero new alerting
   mechanism, matching M-X8's canary precedent for reusing DD-9.

Validation note: full suite 1,232 passed (23 new: 8 `weight_drift.py`
round-trip/drift-detection tests; 13 analyzer/service tests covering
pattern-bucket gating and independence, `RepositoryOutcomeSource`'s as-of
bound, `_resolve_pattern_labels`' real-run-detail resolution, and the
weight-drift alert-dispatch/no-alert-without-baseline paths; 2 CLI tests).
Ruff clean. Also verified directly against the real production
`config/`/`db/athena.db` (using a temporary, since-deleted scratch copy of
`config/` for the drifted-weights case — the real config/db were never
modified): `athena diagnose` against real data now reports on the real
~4,400 decisions already in production (previously always
`no_decision_inputs`); a captured-then-compared baseline correctly showed
no drift when unchanged, and correctly listed both changed values
(`scoring.weights.trend: 20 -> 25`, `scoring.weights.momentum: 20 -> 15`)
when replayed against a genuinely modified candidate config. All
verification artifacts (the real baseline file and diagnostic reports this
testing produced) were deleted afterward — the owner's live system is left
exactly as it was, with no baseline captured until they explicitly choose
to run `athena weight-drift-baseline` themselves.

Architectural note: diagnostics-only, additive. No provider, broker, order,
or frozen-contract change — confirmed by design analysis above, not
assumed twice over. No new persisted schema (file-based baseline, no DB
table). No ADR required.

---

### ATHENA UX Overhaul track closed (2026-07-26): all 9 milestones (UX-1 through UX-9b) approved

Owner-authored 40-point UX/UI audit: transform ATHENA from an "engineering
dashboard" into a professional decision workstation (Bloomberg/TradingView/
Linear/Stripe-grade). Current: 8.2/10 across visual quality, engineering
quality, information architecture, decision UX, product polish. Target:
9.8+/10. Grouped into themed milestones (AI-proposed grouping of the 40
points, owner-confirmed order pending). One explicit exclusion: the
"Place Order" quick action (owner confirmed 2026-07-26 — not required,
conflicts with ATHENA's absolute no-order-placement prohibition anyway).
Two milestones need a small, additive backend piece (no ADR, no domain
change) rather than pure frontend re-skinning — flagged per-row below.

| Milestone | Scope | Backend touch | Status |
|---|---|---|---|
| **UX-1** Hero Decision Card + Executive Summary + Decision Banner | Sticky cockpit becomes an "executive briefing": symbol/stance/score/confidence/risk/R:R at a glance, a 5-line plain-English summary composed from already-persisted engine explanations (never generated), and a one-line recommendation banner. Holding-period and strategy-name fields from the owner's example dropped — confirmed neither exists prospectively anywhere in the backend (research: 2026-07-26) | None | ✅ Approved |
| **UX-2** Score/Confidence/Risk storytelling | Meaning over decimals: risk/score bands (Weak→Excellent), star-rated score contributors, confidence "why ATHENA trusts this" checklist, risk as categorized summary, safety gates as a reassuring checklist, a "Why?" contribution breakdown | None | ✅ Approved |
| **UX-3a** Trade Plan visual redesign | Bigger, cleaner entry/stop/target/R:R presentation; new Expected Return % computed from the plan's own persisted entry/target values | None | ✅ Approved |
| **UX-3b** Chart ATR/moving-average/volume overlay | Chart gains an ATR envelope band, a moving-average line, and a volume bar subplot, all sourced from new `atr`/`moving_average` fields on `CandleDTO` | None (additive DTO fields, additive `atr_series`/`sma_series` functions — existing `atr()`/`sma()` now delegate to them, byte-identical output, verified by the pre-existing indicator test suite) | ✅ Approved |
| **UX-4** Tab renaming + progressive disclosure + Market Context cards | Setup→Trade Plan, Context→Market Context, Response→Decision History (internal `data-brief-tab` keys unchanged); Analysis component breakdown behind a "View detailed breakdown" toggle; regime/market-health render as labeled metric cards instead of a flat chip row | None | ✅ Approved |
| **UX-5** Reasoning Trace redesign | Animated dash-flow connector lines (respects `prefers-reduced-motion`); each stage shows its own real computed state (e.g. Bullish, BUY, Authorized) once that stage's data has loaded, falling back to the generic lifecycle badge when no mapping applies — never fabricated. Per-stage completion/data-quality percentage deferred: only score/confidence/risk persist a `completeness` field, and it's already shown in their existing detail cards; there is no equivalent field for regime/market-health/decision/trade-plan/evidence stages to draw from without inventing one | None | ✅ Approved |
| **UX-6** Sidebar summary + Historical Validation + Decision Timeline narrative + Decision History polish | Sticky right-rail quick summary (symbol/stance/score/confidence/risk pinned to the top of the Reasoning Trace panel); Historical Validation block (win-rate/avg-return/avg-holding aggregate across analog matches — new `DecisionAnalogsDTO` fields, exact arithmetic over each analog's realized `TradeOutcome`); Decision Timeline now narrates a factual stance/score delta per entry instead of a bare timestamp; Decision History shows a friendly "call paid off/didn't pay off" accuracy label wrapping the same real pnl sign | Added `outcome_return_pct`/`outcome_holding_days` to `DecisionAnalogDTO` and `win_rate_pct`/`avg_return_pct`/`avg_holding_days`/`outcomes_sample_size` to `DecisionAnalogsDTO`, computed in `decisions_service.get_decision_analogs` from the `TradeOutcome` already fetched per analog — additive, no schema break | ✅ Approved |
| **UX-7** Typography, spacing, elevation, color-language, micro-animations, accessibility + CSS codebase refactor | Owner requested full design-token normalization plus a proper split of the single 4,903-line `dashboard.css` (was flagged as an unmaintainable monolith). Delivered: (1) lossless split into 14 `css/*.css` files by concern, loaded via an `@import` manifest, verified byte-identical to the original before any value changed; (2) ~85 new design tokens (spacing/typography/elevation/color scales) added by naming every distinct value already in use — zero visual drift, verified by resolving every token back to its literal and diffing against the pre-refactor file (688 changed lines, 0 real mismatches, 2 intentional/verified-equivalent px→rem conversions); (3) accessibility fixes: global `:focus-visible` ring (previously only 5 hand-picked inputs had any focus style), dashboard-wide `prefers-reduced-motion: reduce` coverage (previously only 1 of 4 animations was gated), `aria-label` on 3 icon-only header buttons, `aria-hidden` on the decorative DAG connector SVG, keyboard-operable "Today's Decisions" cards (tabindex/role/keydown, previously click-only) | None (pure frontend refactor + additive tokens; no backend/API change) | ✅ Approved |
| **UX-8** Copy pass | Replaced raw ALL_CAPS enum leakage (TRADE/WATCH/NO_TRADE/INSUFFICIENT_DATA, INCLUDED/EXCLUDED/UNKNOWN) with friendly labels; rewrote dense engineering paragraphs ("persisted"/"config thresholds"/"ingestion"/"generated rationale", the internal "AI Playbook Diagnostics" module name, "deterministic nearest-neighbor...fingerprint") in plain English; fixed several unhelpful empty-state messages; added the market-health explanation sentence (real, already-persisted field) for parity with the regime block, which already had one; renamed hero "Composite score" → "Score" to match the app's own established convention. CLI-command/HTTP-status operational messages were deliberately left as-is — this is a single owner-operator who runs those commands directly, not jargon leaking to a separate non-technical audience | None | ✅ Approved |
| **UX-9** Quick actions + Portfolio Context + export/deep-link/share | Scope resolved with owner: Compare = symbol-vs-symbol side-by-side; Open Chart = enlarge in a modal; deep-link/share deferred to a future enhancement (no existing infra, out of scope here). Split into two reviewable parts | Deep-link/share deferred (documented as future enhancement); Add Watchlist needs a new small backend domain (UX-9b) | ✅ Approved (2026-07-26) — both UX-9a and UX-9b approved |
| **UX-9a** Open Chart / Compare / News / Portfolio Impact | Pure frontend, built entirely on existing endpoints (`?instrument_id=`, `/depth`, `/portfolio`, `/market/instruments/{id}/candles`) — no new backend routes. Open Chart reuses the existing chart renderer in a modal; Compare fetches a second symbol's latest decision + depth and renders side-by-side; Portfolio Impact aggregates open positions for the instrument and computes gain % against the latest real close | None | ✅ Approved (2026-07-26) |
| **UX-9b** Add Watchlist (Saved Symbols) | New minimal owner-curated "Saved Symbols" domain, deliberately independent of two unrelated concepts: the `owner_candidates` pipeline-input validation list (Market Intelligence "Stock List" — saving a symbol here has no ingest/scoring effect) and the automated M4.3 `watchlist` package (config-driven, no owner input at all). New Market Intelligence card: add/list/remove | New `saved_symbols` SQLite table (schema v8) + `SavedSymbolsService` + `GET/POST/DELETE /api/v1/saved-symbols` (mirrors the `owner_candidates` CRUD shape exactly — closer analog than M-X0) | ✅ Approved (2026-07-26) |

---

### Data-integrity fix: REFRESH run_id collision (owner-reported, 2026-07-26)

Not a UX item — a backend correctness bug, tracked separately per owner
instruction. Owner reported Score/Confidence/Risk showing "Unknown"/0.0
for a decision selected from a carousel, fixed only by re-validating it —
and the same happening to whichever OTHER decision had been re-validated
most recently. Root-caused via direct SQLite inspection (`db/athena.db`):
DIXON, TCS, and HFCL's decisions from the same day all shared run_id
`run-refresh-20260724T153000`, but that run's `detail_json.pipeline.
decision_reports` contained an entry for only one of the three.

| | |
|---|---|
| Root cause | `_default_run_id(trigger, as_of)` (`src/athena/scheduling/dry_run.py`) derives the run_id purely from `(trigger, as_of)`. Outside live trading hours, `resolve_validate_as_of` always resolves to the same fixed session-close timestamp, so every ad-hoc "Re-validate" (`RunTrigger.REFRESH`) call on the same day computed the *identical* run_id. `SqliteRepository.save_run`'s upsert (`ON CONFLICT(run_id) DO UPDATE SET ... detail_json=excluded.detail_json`) then silently overwrote the previous call's `decision_reports` with the new call's — orphaning the earlier decisions from their own analysis, which is why they rendered "Unknown" until re-validated again (which just moved the same bug onto whichever symbol was validated *before* it) |
| Fix (part 1) | Append a `uuid4` disambiguator to the run_id for `RunTrigger.REFRESH` only (`run-refresh-{stamp}-{8 hex chars}`), so every ad-hoc validation gets a genuinely unique run_id regardless of `as_of` collapsing to the same value. `PREMARKET`/`CLOSING` are untouched — those are scheduled, at-most-once-per-day cycles where a stable id may be relied on for idempotent retries of the same logical run |
| **Correction (same day)** | Part 1 alone was **incomplete** — confirmed by the owner still seeing "Unknown" values after a successful re-validate. Direct SQLite inspection showed the `runs` table row *did* get a correctly-unique id (part 1 worked for that), but the actual `Decision` row saved to the `decisions` table still pointed at the old, colliding, non-unique id. Root cause: `OwnerValidationPipeline.run()` (`src/athena/ops/owner_validation.py`) independently **recomputed its own local `run_id`** from `(trigger, as_of)` — using the exact same old, collision-prone formula — completely disconnected from the orchestrator's now-fixed, actually-unique run_id. `DryRunPipeline.run()`'s Protocol never had a way to receive the real run_id at all |
| Fix (part 2) | `DryRunPipeline` Protocol and `DryRunCycleOrchestrator.run_cycle()` now thread the orchestrator's own real `run_id` through to `OwnerValidationPipeline.run(..., run_id=run_id)`, which uses it directly instead of recomputing one locally. Every `Decision` saved now correctly points at the exact run whose `detail_json` holds its own analysis — no more silent divergence between "the run record's identity" and "the identity the decision was tagged with" |
| Scope | `src/athena/scheduling/dry_run.py` (`_default_run_id`, `DryRunPipeline` Protocol, `run_cycle`), `src/athena/ops/owner_validation.py` (`run()` signature); no API/DTO/schema change |
| Tests | 2 regression tests in `tests/runtime/test_dry_run_schedule.py` (part 1) + 1 new regression test in `tests/ops/test_owner_validation.py` (`test_repeat_validate_with_same_as_of_does_not_orphan_earlier_decision`, part 2 — validates two different symbols back-to-back with the same `as_of` and asserts each decision keeps its own distinct run_id) + an existing test extended to assert the saved decision's `run_id` matches what was passed in. Full suite **1023 passed** |
| Note | Existing decisions already orphaned by a past collision (this session's TCS/HFCL, and any created between the part-1-only fix and this correction) are not retroactively repaired — see the "Clear all" feature below for a clean-slate path instead |
| Status | ✅ Fixed (both parts), tested, server restarted — awaiting owner confirmation on the live dashboard |

---

### Feature: "Clear all" for Decisions & Trace (owner-requested, 2026-07-26)

Not a UX item — an owner-requested admin utility, tracked separately.
Lets the owner wipe the Decisions & Trace domain and start fresh (e.g.
after the run_id collision above orphaned some test decisions) instead
of re-validating each affected symbol individually. Built as a close
mirror of the existing "Reset fills" (Portfolio) feature — same
CONFIRM-token gate, same automatic pre-delete backup pattern.

| | |
|---|---|
| Scope | Deletes all rows in `decisions`, `decision_traces`, `decision_journal`, `trade_outcomes`. Does **not** touch `runs` (shared with Market Intelligence's universe/regime history), portfolio positions, or owner candidates |
| Backend | `SqliteRepository.delete_decisions_data()`; `DecisionsService.reset_decisions()` (CONFIRM-gated, auto-backup via the same `create_backup` helper Portfolio reset uses, saved as `db/backups/athena-pre-decisions-reset-<timestamp>.db`); `POST /api/v1/decisions/reset` (ADMIN-only) |
| Frontend | "Clear all" button in the Decisions & Trace toolbar → a confirmation modal with a "type CONFIRM to unlock" gate (same UX pattern as Portfolio's reset gate) → "Delete everything" button, disabled until the token matches exactly |
| Tests | 2 new backend tests (confirmation + admin-role gating refuses before touching data; a real clear deletes and a subsequent list is empty) + 6 new dashboard-hosting assertions. Full suite **1022 passed** |
| Status | ✅ Built, tested, server restarted — awaiting owner confirmation on the live dashboard |

### Feature: blocking validate overlay for Decisions & Trace / Market Intelligence (owner-requested, 2026-07-26)

Not a UX item — a correctness/UX fix tracked separately. Owner reported
being able to click other UI mid "Re-validate"/"Validate"/"Add & validate",
risking acting on stale state. Adds a full-viewport, non-dismissible,
ATHENA-branded overlay for the duration of any validate call.

| | |
|---|---|
| Scope | Frontend only — `#validate-overlay` markup + CSS + `showValidateOverlay`/`hideValidateOverlay` centralized inside the shared `validateSymbolsNow`, so all 4 existing call sites (Portfolio row, Market Intelligence row, "Add & validate", Decision Brief "Re-validate") get it automatically |
| Tests | 15 new dashboard-hosting assertions. Full suite **1024 passed** |
| Status | 🔄 Built, tested, visually verified via browser DOM inspection (no owner credentials to trigger a real authenticated validate) — awaiting owner confirmation on the live dashboard |

### Refactor: dashboard.js concern-based split (owner-requested, 2026-07-26)

Not a UX item — a maintainability refactor tracked separately, mirroring
UX-7's `dashboard.css` split. Owner flagged `dashboard.js` at 6,108 lines in
one file. Unlike CSS, the whole file lived inside one
`document.addEventListener("DOMContentLoaded", () => { ... })` closure with
real cross-section coupling (shared mutable state, a 3-way cycle between the
DAG/analysis/context renderers, an auth/api-client cycle) — real ES modules
would have required behavioral code changes at those points with no way to
verify equivalence by diff. Owner chose the lower-risk option instead: split
the source into 22 concern-based files under `static/js/`, reassembled
server-side (new `/dashboard/dashboard.js` route, registered ahead of the
`StaticFiles` mount) into the exact original single-closure script.

| | |
|---|---|
| Scope | `src/athena/api/static/js/00-state-and-dom.js` through `21-bootstrap.js` (+ `_header.js`/`_footer.js` carrying the exact original wrapper boilerplate) — no manual retyping anywhere; every file was mechanically sliced from the original using an Acorn-parsed statement inventory (Node 26 + acorn, installed for this refactor only, not a runtime/build dependency). `src/athena/api/app.py` gains `DASHBOARD_JS_PARTS`/`assemble_dashboard_js()` and a route serving `/dashboard/dashboard.js` by concatenating them in order, read fresh per request (no restart needed to see an edit, same as before) |
| Verification | A standalone Node script parsed the original file into its 372 top-level statements, verified 100% coverage (no gap/duplicate) across the 22-file partition, then re-parsed the reassembled output and did a **content-equality check per statement**: every one of the 372 original statements' exact source text was confirmed present, unaltered, at its new (relocated) position — plus a non-whitespace character-count match end to end. The live server's actual `/dashboard/dashboard.js` response was then diffed against that verified reference: **byte-identical**. Full regression **1031 passed** (new: `test_dashboard_js_assembled_losslessly_from_concern_split`, which re-derives the expected assembly from the real files on every test run — never a frozen snapshot). Live browser check: zero console errors on load; all 5 tabs exercised via real click-wired handlers (not synthetic DOM pokes) with only the expected, pre-existing unauthenticated-API-call error logging (since no owner credentials were available to authenticate), no ReferenceError/TypeError/SyntaxError anywhere |
| Status | ✅ Built, verified, live-tested — old monolithic `dashboard.js` deleted (fully superseded) |

### Fix pass: stale Reasoning Trace sidebar + tab restored on login (owner screenshot, 2026-07-27)

Two bugs the owner found via live screenshots.

| | |
|---|---|
| Bug 1 | After "Clear all" (Decisions & Trace), the main brief correctly went empty but the Reasoning Trace sidebar kept showing the previously selected symbol's quick-summary chips (score/confidence/risk) and DAG stage-detail card ("Regime / COMPLETED / regime-NIFTY 50-..."). Root cause: `renderSidebarQuickSummary()` already correctly hides itself when there's no active decision, but nothing re-invoked it after Clear all nulled the decision state, and the DAG stage-detail panel had no reset path at all. Fix: `renderDecisionBriefEmpty()` — the one function whose job is "there is no decision to show" — now authoritatively nulls `activeDecisionData`/`selectedStageId`, re-invokes `renderSidebarQuickSummary()`, and hides the DAG details panel, so every caller (Clear all, zero-filter-results, a failed decision-detail fetch) is covered, not just the one path the owner happened to hit |
| Bug 2 | Login sometimes reopened whatever tab was active before instead of always landing on Portfolio Overview. Root cause: `initializeRoute()` read `window.location.pathname` to pick a tab — if the browser's address bar still pointed at e.g. `/dashboard/decisions` (left over from a prior session), login honored that stale URL. Fix: `initializeRoute()` now always resets to `/dashboard/overview` and switches to Overview, mirroring the reset the logout handler already did |
| Tests | 4 new dashboard-hosting assertions. Full suite **1031 passed** |
| Status | ✅ Built, verified via code-level correctness (both fixes are small, unconditional, no branching) + a live check confirming `history.replaceState` behaves as expected in-browser. Could not drive a real authenticated login/Clear-all end-to-end myself (this deployment requires real owner credentials) — awaiting owner confirmation on the live dashboard |

### ATHENA Workstation Refactor (owner assignment + reference mock, 2026-07-27)

Presentation-layer-only refactor of Decisions & Trace to match a reference
"professional trading workstation" mock — reposition existing information,
never invent new. No backend/business-logic/scoring/reasoning changes in
any of DT-1 through DT-4. Split into 4 reviewable milestones per the
milestone-workflow discipline; one in flight at a time.

Owner-confirmed scope decisions (before DT-1 started):
- Tabs split into 5 (Trade Plan / Analysis / Market Context / Response /
  History) rather than keeping today's 4 — Response = Journal/Outcome only,
  History = Timeline (moved from the always-visible hero) + Analogs (DT-3).
- Market ticker strip (NIFTY/BankNifty/VIX/breadth) approved as a header
  addition, with a strict data-source priority: reuse ATHENA's existing
  Kite/Regime/Market-Health pipeline data first; a genuinely new external
  feed is only a last resort requiring its own stop-and-propose gate (DT-2).
- "Similar Trades" mini sparkline approved — reuses each analog's
  already-fetched `outcome_return_pct` (DT-4).
- Two nav placeholders ("Reports & Analytics", "Settings") added as visibly
  disabled, no backing route — explicitly future-implementation (DT-1).

| Milestone | Scope | Status |
|---|---|---|
| **DT-1** Layout shell — 3-pane workstation | Replaced the horizontal outcome carousels + toolbar-above-the-fold layout with a permanent left Symbols panel (search always visible, collapsible BUY/WATCH/PASS-equivalent groups, strong selected-row highlight) beside the center detail (now immediately visible, zero scroll) and the existing right Reasoning Trace (untouched — its redesign is DT-4). Same data/selection/filter/sort/dismiss logic throughout — only the DOM position and row/group markup shape changed | ✅ Approved |
| **DT-2** Hero header + Quick Summary + ticker strip | Hero header spacing/hierarchy polish; standalone Quick Summary card with Trade-Plan/Historical-Analogs fields (real Holding Period range, not a single average) and reference-mock-matched formatting/coloring; header market ticker (NIFTY 50/BANK NIFTY/INDIA VIX, real level + real day-change %, 60s auto-refresh) | ✅ Approved |
| **DT-3** Tab restructuring (5 tabs) + spacing polish | Split "Decision History" into Response (Journal/Outcome) + History (Timeline + Analogs); Decision Timeline moved out of the always-visible hero (real wasted-space fix); Recommendation+ATHENA Summary hero redesign; identity row redesign (real company name via a small ingestion fix, star favorite toggle, overflow menu); symbols panel color system calibrated to a single, restrained scheme | ✅ Approved |
| **DT-4** Reasoning Trace redesign + Similar Trades sparkline | Replace the auto-fit-grid + SVG-connector DAG with a cleaner vertical pipeline list (real existing stage status only, never fabricated counts/funnels — confirmed no such data exists anywhere in ATHENA); same click/detail-panel behavior, same stage order; add the last-5-trades sparkline to Analogs | ✅ Approved |

**ATHENA Workstation Refactor track closed (2026-07-27):** owner approved DT-4, the last of the 4 milestones (DT-1 through DT-4). The full presentation-layer refactor of Decisions & Trace — 3-pane layout shell, hero header + Quick Summary + market ticker, 5-tab restructuring + identity row + symbols-panel color system, and the Reasoning Trace vertical pipeline list + Similar Trades sparkline — is complete. No backend/business-logic/scoring/reasoning changes were made in any of the four milestones; every new visual element traced back to real, already-persisted data (or was explicitly omitted and tracked as future scope when no real data existed, per ADR-005).

### ATHENA Market Intelligence Redesign (owner assignment + reference mock, 2026-07-27)

Full redesign of the Market Intelligence tab into a "Market Command Center," matching the design language, component hierarchy, and workstation layout established by the ATHENA Workstation Refactor above. Same golden rule as that track: reuse existing ViewModels/APIs/business logic wherever possible, never fabricate a value with no real data source — hide the field instead and track as future scope. Split into 5 reviewable milestones; one in flight at a time.

**Reference mock:** `docs/design/ATHENA-MARKET-INTELLIGENCE-REFERENCE.jpg` (committed to the repo — the primary visual target for MI-2 through MI-5, especially the still-unbuilt Validation Pipeline funnel, Universe table, and Recent Activity/Quick Actions layouts in MI-3–MI-5). Sibling reference for the earlier Decisions & Trace track: `docs/design/ATHENA-DECISION-TRACE-REFERENCE.jpg`. Per this track's own rule, the mock is directional, not literal — omit/hide anything it shows with no real backing data.

Before any implementation, a full data-source inventory was done across every mock element (see MI-2 below for the two biggest findings). Owner-confirmed scope decisions (before MI-1 started):

- Market Health Score ("84/100" ring) and Breadth ("72%"/"1458/526") are both confirmed gaps (hardcoded `0`/`0` upstream, no numeric `MarketHealthScore` ever constructed anywhere in the codebase) — owner chose to show the real 4-dimension categorical labels `MarketHealthEngine` already computes instead of either fabricating a number or omitting the section entirely (MI-2). **Post-MI track:** both gaps are now owned by **Market Metrics Completion** (MH-0+), with locked owner choices: universe ADV/DEC/neutral breadth, exact F-5 six-component score, external FII/DII for institutional strength.
- Recent Market Activity will be a real chronological feed (validation runs + VIX/index snapshot history) — no synthesized "regime reaffirmed"/"breadth improved" diff-events, since no comparison logic for those exists anywhere (MI-5).
- Universe table's Sector column — a fixable gap (same shape as DT-3's company-name fix): the seed CSV's real `Industry` column is silently discarded during ingestion. Owner approved fixing it (MI-4).
- "Run Full Validation" — a real engine (`OwnerValidationPipeline.run()`) with zero endpoint/button today; owner approved wiring a new endpoint despite it being the one mutating (not just read) action in this otherwise presentation-only redesign (MI-5).
- Trading Calendar relocated to a collapsed-by-default secondary panel on the same page (not moved to Settings/a new Utilities section) — it previously consumed the largest area on the page for one of the lowest-value sections during live trading (MI-1).
- "Export Market Snapshot" and the Validation Pipeline's "Filtered" stage are lower-stakes calls proceeding on stated defaults: Export omitted entirely (the export type genuinely isn't implemented — matches the "hide, don't fabricate" rule); "Filtered" shown as a derived rollup (Eligible − Watch − Trade, pure arithmetic over already-real counts, no new data).

| Milestone | Scope | Status |
|---|---|---|
| **MI-1** Shared ticker strip + Trading Calendar relocation | Generalize the Decisions & Trace header ticker to also render on Market Intelligence (one shared component/endpoint via `TICKER_TABS`, not two); relocate Trading Calendar out of the primary grid into a collapsed-by-default `<details>` panel, same rendering functions/ids untouched | ✅ Approved |
| **MI-2** Market Summary Hero + Market Regime & Context | Larger-presentation Trend/Volatility/Gap/Evidence Attribution (real); Market Health Score/Breadth gap handled via real categorical labels | ✅ Approved |
| **MI-3** Validation Pipeline funnel | New small dedicated endpoint exposing the already-computed Universe→Evaluated→Eligible/Excluded→decision_counts breakdown as a typed 5-stage funnel | ✅ Approved |
| **MI-4** Universe table redesign | Reuse real Symbol/Status/Actions; add Sector via the ingestion fix; scope Eligibility-per-row/Last-Validated-per-row | ✅ Approved |
| **MI-5** Recent Activity + Quick Actions + Saved Symbols | Real chronological activity feed; Quick Actions consolidated (Add Symbol reuse, new Run Full Validation endpoint, Refresh Market Data relabeled honestly, Export omitted); Saved Symbols relocated to a secondary panel. Also absorbs the owner-requested "Validate All" — same operation as Run Full Validation — plus Kite pacing/429 handling | ✅ Approved |

#### MI-1 — Shared ticker strip + Trading Calendar relocation

A full data-source inventory (file:line level) was done across every element in the reference mock before proposing any milestone breakdown — see the track intro above for the two biggest findings (Market Health Score/Breadth are both confirmed gaps). MI-1's own scope was narrowed from the originally-proposed "2-row workstation grid" down to just the two independently well-defined, zero-placeholder pieces: building the full target grid now would leave empty cells for Quick Actions/Recent Activity (content that doesn't exist until MI-5), which conflicts with the project's "no placeholders" rule. The grid will take its final shape incrementally as MI-2 through MI-5 land real content, mirroring how DT-1→DT-4 organically built up the Decisions & Trace layout.

| | |
|---|---|
| Scope | `03-app-shell.js`: `TICKER_TABS = new Set(["decisions", "market"])` replaces the hardcoded `tabId !== "decisions"` check in 3 places (visibility, refresh start/stop, `loadTabData`'s market branch now also calls `loadMarketTicker()`). `index.html`: Trading Calendar markup moved out of the 3-column `.market-workstation` grid (now 2 columns) into a `<details class="market-calendar-details">` panel below it, collapsed by default — same ids (`calendar-month-year`/`calendar-grid-container`/`upcoming-events-container`) so `renderCalendar()`/`renderUpcomingEvents()` are completely untouched. `06-market-intelligence.css`: `.market-workstation` grid-template-columns `1fr 1.2fr 1fr` → `1fr 1fr`; new `.market-calendar-details`/`.market-calendar-summary`/`.market-calendar-chevron` (native `<details>`, no JS toggle logic needed). |
| Tests | ~15 new/updated dashboard-hosting assertions (ticker generalization across all 3 coupling points, calendar relocation, 2-column grid). Full suite **1042 passed** |
| Coverage | Live-browser verified: ticker strip now visible on Market Intelligence tab (confirmed via a real nav click, not a synthetic poke); 2-column grid renders correctly; calendar panel collapsed by default, expands on click with the chevron rotating, calendar content (month grid, upcoming events) renders correctly once expanded; zero uncaught console errors beyond the expected unauthenticated-fetch logging already present in every prior milestone's verification |
| Status | ✅ Approved (2026-07-27) |

---

#### MI-2 — Market Summary Hero + Market Regime & Context

Replaced the "Volatility Regime & Health" card with a "Market Summary" hero. Investigated the Market Health Score gauge before touching any UI: `owner_validation.py`'s `_regime_to_payload()` hardcoded `"market_health": 0` in the payload the page reads, and the real `MarketHealthEngine.assess()` result — already computed during every scan — was never serialized back into it. Deeper still: `MarketHealthScore` (the frozen domain's numeric 0-100 type) has zero constructors anywhere in ATHENA; there is no real number to show at all, only `MarketHealthAssessment.dimensions` (4 real categorical labels: breadth/trend_quality/momentum/volatility). Per the owner's decision, replaced the fabricated gauge with these real labels instead of omitting the section or inventing a placeholder.

Fixing this required two backend changes, not one — caught only by re-running the test after the first fix:

1. `_regime_to_payload(regime, market_health=None)` now builds a real `dimensions` dict from the passed `MarketHealthResult` (empty `{}`, never fabricated, when none is available). `reg_stage` in `_scan_eligible` reordered so `market_health` is computed before the payload is captured (previously the payload was built one line before `market_health` was assigned, on the very first instrument of every scan).
2. That alone didn't reach the frontend: `run()` computes an eager, regime-only `regime_payload` via `_maybe_regime()` *before* any scan runs, and only fell back to the scan's own richer `scan_regime` (with real `market_health`) `if regime_payload is None` — which was essentially always false, so the eager payload (never carrying market_health) silently won every time a scan had eligible symbols. Flipped the precedence to prefer `scan_regime` whenever a scan actually ran.

Verified against the real production `db/athena.db` (not just synthetic tests): ran `OwnerValidationPipeline.run()` directly for a real symbol and confirmed `regime_assessment.market_health` came back as `{'breadth': 'BREADTH_UNKNOWN', 'trend_quality': 'MIXED_TREND_QUALITY', 'momentum': 'WEAK_MOMENTUM', 'volatility': 'VOLATILITY_NORMAL'}` — a real dict, not `0`.

| | |
|---|---|
| Scope | **Backend**: `src/athena/ops/owner_validation.py` — `_regime_to_payload()` signature + body, `reg_stage` ordering, `run()`'s `regime_payload`/`scan_regime` precedence. **Frontend**: `index.html` — card renamed "Market Summary" with an as-of timestamp; Trend/Volatility/Gap rebuilt as `.brief-gauge`/`.hero-metric-band` tiles (the exact same tile language as Decisions & Trace's hero gauges, not a new one); Market Health rebuilt as a `.context-metric-grid` (the exact same cards the Decision Brief's own Market Context uses). `09-market-intelligence.js` — new `renderMarketHealthGrid()` reusing `contextMetricCard`/`contextChipTone`/`friendlyLabel` verbatim from the Decision Brief's context rendering (one tone system for the same RegimeLabel/MarketHealthLabel enums, not two parallel ones); `regimeAsOf` tracked and rendered; the old parallel bull/bear/neutral tone-classification logic removed in favor of `contextChipTone`; each of Trend/Volatility/Gap now falls back to its own `*_UNKNOWN` sentinel instead of a specific fabricated state (previously an absent field defaulted to "Normal volatility"/"No gap" — an assessed-looking state for data that was actually just missing). `07-decision-format.js` — `formatVolatilityLabel()` removed (its only caller was replaced). `06-market-intelligence.css` — dead `.regime-badge`/`.regime-field`/`.health-*` rules removed; new `.market-summary-gauges` (3-equal-column grid) and a scoped label-wrap override (`.brief-gauge-label` defaults to single-line ellipsis tuned for a 4-column grid's short labels — 3 columns here are narrower still, and "Volatility" alone could truncate at real workstation widths). |
| Tests | New `tests/ops/test_owner_validation.py` assertion locking in the real 4-dimension `market_health` dict. ~30 new/updated dashboard-hosting assertions. Full suite **1042 passed** |
| Coverage | Live-browser verified after a required server restart (backend Python touched): real production-data confirmation via a direct `OwnerValidationPipeline.run()` call (above); frontend rendering confirmed using that exact real payload — Trend/Volatility/Gap tiles tone-colored correctly (Bear Trend/Gap Down red, Normal Volatility neutral), Market Health's 4 real dimension cards rendered with correct tones (Mixed Trend Quality amber, Weak Momentum red, Breadth Unknown muted). Caught and fixed a real truncation bug via DOM measurement (not just eyeballing): tile labels clipped at realistic narrower workstation widths — fixed with shorter labels + a scoped wrap override, then re-measured to confirm zero truncation. Zero uncaught console errors beyond the expected unauthenticated-fetch logging. |
| Status | ✅ Approved (2026-07-28) |

---

#### MI-3 — Validation Pipeline funnel

Replaced the "Today's Validation" text summary strip with a horizontal 5-stage Validation Pipeline funnel matching the Market Intelligence reference mock. Added a small READ endpoint that maps the already-persisted `validation_summary` on the latest successful owner_validation run into typed stages — no new scan, no mutation, no fabricated upstream "Filtered" field.

| | |
|---|---|
| Scope | **Backend**: `ValidationFunnelDTO`/`ValidationFunnelStageDTO`; `PipelinesService.validation_funnel()`; `GET /api/v1/pipelines/validation-funnel`. Stages Universe→Eligible→Filtered→Watch→Trade; Filtered = `max(0, eligible − WATCH − TRADE)`; `% of Universe` with `None` when Universe is 0. **Frontend**: card renamed "Validation Pipeline"; `#validation-funnel` horizontal stage row (Trade accented); View Details toggles existing Eligible/Excluded + Qualified panels (preserved until MI-4); parallel fetch alongside `/pipelines/runs`. |
| Tests | 3 new pipeline API tests (empty / Filtered math + newest-run preference / auth). ~20 new dashboard-hosting assertions. Full suite **1045 passed** |
| Coverage | Live-verified: funnel populated after host restart (real production validation_summary); UI polish iterations for mock alignment, viewport scroll, and stacked Inspect Trace modal. |
| Status | ✅ Approved (2026-07-28) |

---

#### MI-4 — Universe table redesign + Sector ingestion fix

Replaced the Stock List (symbol + Validate/Remove) with the mock’s Universe table. Sector comes from the Nifty 500 CSV `Industry` column that `parse_nifty_constituent_csv` previously discarded — same class of fix as DT-3’s company-name ingestion, but sourced from the seed CSV (Kite has no sector). Last Validated uses the latest real `decisions.ts` per symbol (no new write-path field).

| | |
|---|---|
| Scope | **Backend**: `Instrument.sector`; SCHEMA_VERSION 9→10 + idempotent migration; `parse_nifty_constituent_rows()`; seed backfills sector even on once-per-day skip; kite upserts preserve existing sector; `OwnerCandidateDTO` enriched with `sector`/`status`/`eligibility_summary`/`last_validated_ts` via `CandidatesService` (no new endpoint). **Frontend**: Stock List → Universe table (Symbol/Sector/Status/Eligibility/Last Validated/Actions) with status+sector filters; Validate/Remove/Inspect Trace actions. |
| Tests | Sector parse/migration/preserve/backfill; candidates enrichment; scoped-validate verdict merge; Qualified Today dedupe (write + read path). Full suite **1055 passed** |
| Coverage | Self-verified via tests, plus replayed against a copy of the live DB: 16 Eligible / 10 Excluded / 481 Pending with real per-symbol timestamps, Qualified Today collapsed to one row per name, and the seed path backfilling sector onto 500 instruments (20 distinct sectors). Live: restart the host — a host started before these files were saved serves the old Python and shows every row Pending — then `./athena-daily` for the sector backfill. |
| Owner-reported fixes | Universe status no longer collapses to Pending after a scoped validate (per-symbol verdict merged newest-run-first, Excluded rows take Last Validated from the judging run); Qualified Today keeps one row per symbol (newest same-day verdict), so repeat validates stop duplicating names. |
| Status | ✅ Approved (2026-07-28) |

---

#### Fix pass: unlisted candidate symbols (owner-reported, 2026-07-28)

`./athena-daily` aborted with `ERROR: kite symbols not found on NSE: ['INFSDFSD']` — a typo'd candidate, added through the dashboard, blocked every subsequent cycle for the whole 507-symbol universe. Two separate defects: nothing stopped an unlisted symbol from being stored, and the provider treated a candidate scope list like configuration.

| | |
|---|---|
| Scope | `kite_provider.py`: `strict_symbol_filter` (default `True`) — `kite.json`'s own symbols still fail loudly, while a caller-supplied scope no longer raises; `factory.py` passes `strict_symbol_filter=kite_symbols is None`, so the CLI's existing resolve-and-warn path (and `validate_symbols`' own 422) is finally reachable. `symbol_validate.py`: catalog resolution extracted into `resolve_against_catalog()` (one catalog fetch, reused by its caller). `candidates_service.py`: `upsert_candidate` rejects a symbol the exchange does not list (422, nothing persisted), best effort — an unreachable catalog allows the add. `owner_validation.py`: a candidate with no catalog row and no ingested bar is reported in a new `unresolved_candidates` detail key instead of being judged as a synthesized instrument (which read as "Excluded: failed rules"). `candidates_service.py`/`sqlite_providers.py`/`index.html`/`09-market-intelligence.js`/`06-market-intelligence.css`: new `UNRESOLVED` status, badge, and filter option in the Universe table. |
| Tests | Provider strict/non-strict filter behaviour; pipeline reports-not-judges an unresolvable candidate; service maps `unresolved_candidates` → `UNRESOLVED` while a never-validated symbol stays `PENDING`; add-time rejection persists nothing; add proceeds when the catalog cannot be consulted. Full suite **1064 passed** |
| Coverage | Reproduced from the owner's own `./athena-daily` failure and replayed against a copy of the live DB. |

---

#### Fix pass: Validation Pipeline shows the day, not the last run (owner-reported, 2026-07-28)

Owner: "validation pipeline always lists only recent symbol and overrides previous one — I want the previous validation list as well." A scoped validate writes a run whose `universe_members` holds only the symbol it was asked about, so the funnel collapsed to "Universe 1 Symbols" and the details modal listed that one name, hiding everything validated earlier the same day.

| | |
|---|---|
| Scope | `owner_validation.py`: `_qualified_from_repo()` no longer restricts the day's WATCH/TRADE decisions to the current run's own symbols (still newest verdict per symbol, so a name downgraded to NO_TRADE drops out). `pipelines_service.py`: `validation_funnel()` counts distinct symbols across the day's completed runs, each keeping the verdict of the newest run that covered it, with each symbol's WATCH/TRADE read from that same run — never summed per-run counts, which would count re-validations twice; runs that recorded counts without per-symbol members keep the previous summary-based reading. `09-market-intelligence.js`: the details modal merges the day's runs by the same rule, so its Eligible/Excluded and Qualified Today lists match the funnel. |
| Tests | Funnel merges the day's runs and ignores a previous day's; re-validating replaces a symbol's verdict rather than adding a row; Qualified Today keeps symbols from earlier runs, one row per symbol, same day only. Full suite **1064 passed** |
| Coverage | Replayed against a copy of the live DB: the funnel went from Universe 1 / Eligible 1 (the last scoped validate) to Universe 16 / Eligible 9 / Watch 5 / Trade 4 for the day, reconstructed from runs already persisted — no re-validation needed. |

---

#### MI-5 — Recent Activity + Quick Actions + Full Validation (ADR-007)

Closes the Market Intelligence redesign. Delivers the mock's Quick Actions and Recent Activity, relocates Saved Symbols to a secondary panel, and wires **Run Full Validation / Validate All** as one owner-triggered background job per ADR-007 — with Kite pacing + 429 retry so a 507-symbol run does not trip the vendor.

| | |
|---|---|
| Scope | **Pacing**: `KiteRateLimitConfig` in `kite.json` / `KiteProviderConfig`; `UrllibKiteTransport` enforces per-class min intervals (historical 3/s, quote 1/s, other 10/s) and bounded 429 backoff. **Job**: `ServeRuntime.full_validation` + `ops/full_validation.py` (daemon thread, `CycleRunnerLock` single-flight, own DB connection); `POST/GET /api/v1/market/validate-all` (202 / poll); `CycleBusyError` → 409. Scoped `POST /market/validate` unchanged. **UI**: mock-aligned seven-cell Market Summary row (three regime metrics + four real categorical health dimensions) and Evidence footer; compact Validation KPI blocks beside the primary Universe workspace (~63% main width, sticky-header internal scroll); utility rail ordered Recent Activity → Saved Symbols → Quick Actions; Run Full Validation / Validate All / Add Symbol / Refresh Market View preserved. Export omitted (not implemented). |
| Tests | Transport pacing + 429 retry; full-validation lock/busy guards; validate-all 202/409 API; dashboard hosting for new controls. Full suite **1072 passed** |
| Coverage | Self-verified via tests and static browser measurement at 1920×1080: Universe 818px of 1304px main width (62.7%) with 553px visible internal table viewport; Summary 172px; compact Pipeline 173px. Assets `v9.62.0`; full-validation progress polls every 3s. |
| Status | ✅ Approved (2026-07-28) |

**ATHENA Market Intelligence Redesign track closed (2026-07-28):** owner approved MI-5, the last of the 5 milestones (MI-1 through MI-5). Presentation-layer Market Command Center is complete: shared ticker, Market Summary categorical hero, Validation Pipeline funnel, Universe table + sector ingestion, Quick Actions / Recent Activity / Saved Symbols rail, and ADR-007 full-universe validation with Kite pacing. Confirmed data gaps that the mock still shows literally — numeric Market Health Score (F-5) and real breadth ADV/DEC — move to the **Market Metrics Completion** track below (never fabricated in MI).

---

### Market Metrics Completion (owner assignment, 2026-07-28)

Literal Market Summary mock fidelity requires real numeric inputs the MI track deliberately deferred (ADR-005). Owner decisions locked before MH-0:

- **Breadth:** Nifty-500 / owner-universe advances vs declines from latest two D1 closes; unchanged closes count as **neutral** (not exchange-wide NSE breadth; Kite cannot supply that).
- **Market Health Score:** exact frozen F-5 six components — `trend_quality`, `breadth`, `liquidity`, `volatility`, `institutional_strength`, `gap_stability` — not a four-label rollup and not a display-only mapping.
- **Institutional strength:** external FII/DII cash-flow source (no price-volume proxy).

| Milestone | Scope | Status |
|---|---|---|
| **MH-0** Design — FII/DII source + F-5 scoring contract | DD-11 institutional-flow source decision; ADR-008 (provider Protocol); F-5 scoring / unknown-data / persistence / API history specification | ✅ Approved |
| **MH-1** Canonical inputs + persistence | Approved FII/DII ingest; universe breadth (+ neutral); liquidity + gap-stability aggregates; snapshot/history read paths | ✅ Approved |
| **MH-2** Exact F-5 `MarketHealthScore` | Construct + persist authoritative six-component score; align scoring/risk/decision consumers; ADR-005 evidence | ✅ Approved |
| **MH-3** Market Summary API + mock-faithful UI | Dedicated summary read model; sparklines/rings/ADV-DEC/evidence panel from real persisted data only | ✅ Approved |

Design artifacts (MH-0):

- `docs/decisions/DD-11-institutional-flow-fii-dii.md` (Accepted)
- `docs/adr/ADR-008-institutional-flow-provider.md` (Accepted)
- `docs/design/F5-MARKET-HEALTH-SCORE.md` (Accepted)

#### MH-1 — Canonical inputs + persistence

Delivers the real inputs F-5 needs before any numeric score is constructed: institutional FII/DII rows, universe ADV/DEC/neutral breadth on `MarketSnapshot`, liquidity + gap-stability aggregates, and snapshot history reads.

| | |
|---|---|
| Scope | **Domain**: `InstitutionalFlowSession`; `MarketSnapshot.breadth_neutral` (blueprint §4 additive). **Provider**: `InstitutionalFlowProvider` Protocol; file + NSE adapters; config `ingestion.institutional_flow_provider`. **Persistence**: SCHEMA_VERSION 11 `institutional_flows` append-only; `list_snapshots_recent`; flow query helpers. **Pure aggregates**: `market_health/aggregates.py` (breadth/liquidity/gap). **Wiring**: ingest best-effort institutional fetch (never aborts cycle); owner validation enriches snapshot + persists `market_metric_inputs` on run detail. |
| Tests | File/NSE parse+provider; repository flow + snapshot history; breadth/liquidity/gap pure tests; SCHEMA_VERSION 11. Full suite **1081 passed** |
| Coverage | Self-verified via unit/integration tests. Live NSE fetch is best-effort (ProviderError → `institutional_error`, cycle continues). Flip `institutional_flow_provider` to `nse` when ready for live FII/DII. |
| Status | ✅ Approved (2026-07-28) |

#### MH-2 — Exact F-5 `MarketHealthScore`

Constructs the authoritative six-component numeric score from MH-1 inputs, persists it on the validation run, and cuts scoring's `market_quality` over to `MarketHealthScore.total` when present.

| | |
|---|---|
| Scope | **Config**: F-5 component point maps + weights (sum 100). **Pure construction**: `market_health/score.py` maps trend/breadth/liquidity/volatility/institutional/gap → points or absent; emits `MarketHealthScore` only when all six present (F-5 §4). **Persistence**: run `detail_json.market_health_score` (+ component diagnostics). **Cutover**: `ScoringEngine._market_quality` prefers score total; categorical label average remains compat shim. |
| Tests | Component band mapping, unavailable-when-any-absent, weighted total, scoring cutover, config validation. Full suite **1091 passed** |
| Status | ✅ Approved (2026-07-28) |

#### MH-3 — Market Summary API + mock-faithful UI

Dedicated read model exposes persisted F-5 score, universe breadth, VIX, and sparklines; Market Summary UI renders them honestly (Unavailable when absent).

| | |
|---|---|
| Scope | **API**: `GET /api/v1/market/summary` + `MarketSummaryDTO` (F-5 §8). **Service**: reads latest completed validation run detail (`market_health_score`, `market_metric_inputs`, `regime_assessment`) + D1 candle closes for sparklines. **UI**: mock-aligned single 8-cell band — Regime (NIFTY sparkline), Volatility (VIX sparkline), Gap indicator, real Universe Breadth ring, categorical Momentum/Trend/Volatility indicators, and persisted F-5 Market Health ring; concise display labels remove only redundant dimension words. |
| Tests | Service unit + authenticated HTTP + dashboard hosting assertions. Full suite **1095 passed** |
| Status | ✅ Approved (2026-07-28) |

**ATHENA Market Metrics Completion track closed (2026-07-28):** owner approved MH-3, the last of the 4 milestones (MH-0 through MH-3). Canonical FII/DII + universe breadth inputs, exact F-5 `MarketHealthScore`, and the dedicated Market Summary read model + mock-faithful 8-cell UI are complete. Unavailable Breadth / Market Health remain honest empty states until a post–MH-1/MH-2 validation writes complete metric inputs and a six-component score — never fabricated (ADR-005).

---

| | |
|---|---|
| Scope | `index.html`: new `.decisions-workstation` (3-column grid) replacing `.trace-workstation` (2-column); new `.symbols-panel` (search + icon-triggered filter/sort/clear-all popover + summary strip + collapsible outcome groups), replacing the old toolbar card + `#decisions-carousel-groups` carousel container. `12-decisions-list.js`: `renderDecisionCarousels` rewritten to build vertical rows instead of a horizontal scroll-snap track (nav-arrow buttons and `wireCarouselOverflow` removed as dead code); `renderDeckCard` renamed `renderSymbolRow`; left-panel scroll position preserved across re-renders. `13-decision-brief-core.js`'s `selectBriefing`: resets only the center panel's scroll to top on a new selection, leaves left/right panels untouched. `09-decision-brief-shell.css`/`12-decision-cards-dag.css`: new grid + row/group styling, strong selected-state (accent wash, left indicator, glow, bolder symbol text). Two disabled nav placeholders added to the global sidebar |
| Tests | 2 new dashboard-hosting assertions sets (structural markup/CSS/JS presence + a real div-nesting-depth check for the filter popover, which caught a real bug — see below). Full suite **1031 passed** |
| Coverage | Live-browser verified: 3-pane layout renders correctly with zero scroll to reach the detail panel; injected sample decision data to confirm row/group rendering, selected-row highlight, and collapse-toggle all match the reference mock; verified the responsive single-column collapse below 1400px; confirmed zero console errors (only the expected, pre-existing unauthenticated-API-call logging, since no owner credentials were available) |
| Status | ✅ Built, tested, live-verified |

**Bug caught and fixed during live verification**: the filter popover initially rendered off-screen, anchored to the wrong ancestor — it was a DOM *sibling* of `.symbols-panel-header` rather than a *child*, so its `position: absolute` resolved against an unrelated ancestor instead of the header. Fixed by nesting it inside the header in the HTML; added a test that checks actual div-nesting depth between the two elements (not just that both class names exist somewhere in the page), so this exact regression can't silently reappear.

**Fix pass (owner live screenshots, 2026-07-27)** — four refinements to the filter popover, found once the owner tried it on real data:
1. Excessive vertical gaps between Stance/Type/Sort: each `<label class="decisions-filter-label">` was inheriting `flex: 1 1 100px` from an unrelated shared rule written for the old horizontal toolbar (`05-portfolio.css`), which stretched each label to fill the popover's height inside this new vertical flex layout. Pinned to `flex: none`.
2. "Clear all" moved out of the popover entirely into its own separate, danger-styled icon button — sitting inside a view-only filter panel, it read as "clear the filters" rather than "wipe my decisions."
3. Added an explicit "Reset" (view only — stance/type/sort back to defaults, distinct from "Clear all" which deletes data) and a close (×) button — the filter icon toggle was previously the only way to dismiss the popover, which the owner flagged as undiscoverable. Reset also dismisses the popover afterward (owner follow-up).
4. Added a backdrop behind the popover, scoped to the list area only (the header stays outside it and interactive) — previously the symbol list stayed fully visible *and clickable* underneath the open popover, with no visual differentiation. Verified via `elementFromPoint` in a live browser that the backdrop itself, not the list, receives clicks in that region.

11 new dashboard-hosting assertions. Full suite **1031 passed**.

### Fix pass: reload-resets-tab regression + collapsible global sidebar (owner-requested, 2026-07-27)

Not Decisions & Trace-specific — global app-shell fixes, requested before starting DT-2.

| | |
|---|---|
| Bug | The earlier "tab restored on login" fix (see the fix-pass entry above this one) made `initializeRoute()` *always* force Portfolio Overview — correct for a fresh login, but the owner reported it also made a **plain reload (Cmd+R)** of an already-active session jump back to Overview every time, which they flagged as "very annoying." Root cause of the over-fix: `initializeRoute()` is called from 3 places — `bootstrapSession()`'s two silent-restore branches (auth not required; an already-valid stored token) **and** the login-form submit handler — and the original fix changed the shared function instead of only the login path |
| Fix | `initializeRoute()` reverted to URL-preserving (parses `window.location.pathname`, used by both `bootstrapSession()` branches — a reload now stays on whatever tab was already showing). A new, separate `resetToOverviewTab()` (force-to-Overview) is called only from the login-form submit handler — the one place that should actually reset navigation |
| Feature | Collapsible global sidebar — icon-only when collapsed (each nav item already had visible text as its label; added `title="..."` attributes so hovering still shows it as a tooltip once collapsed). `.console-main` (`flex-grow: 1`) reflows into the freed width automatically via the same CSS width transition on `.sidebar` — no JS recalculation needed. Preference persisted in `localStorage` across reloads |
| Tests | 6 new dashboard-hosting assertions (including one that explicitly greps `initializeRoute`'s own function body to confirm it does *not* contain the force-reset call, so this exact regression can't silently reappear) |
| Coverage | Live-browser verified: sidebar collapses/expands with a smooth width transition, main content reflows automatically, toggle icon flips direction, collapsed state survives a reload. Could not drive the real reload-preserves-tab scenario end-to-end myself — this deployment requires real owner credentials (confirmed via the unlock gate staying visible) — verified via direct code review instead, since both `initializeRoute`/`resetToOverviewTab` are small, unconditional functions with no branching |
| Status | ✅ Built, tested, live-verified (sidebar collapse); awaiting owner confirmation of the reload-tab-persistence fix on the real authenticated session |

#### DT-2 — Hero header + Quick Summary + ticker strip

Before implementing the ticker, stopped and researched exactly what market data ATHENA already has (per the owner's data-source priority), then presented two genuine gaps for a decision rather than fabricating either:

- **Market breadth (ADV/DEC)**: confirmed a genuine gap, not a wiring gap — Kite Connect's quote API has no advancers/decliners concept, and the live Kite provider hardcodes `breadth_advances=0, breadth_declines=0` always. **Decision: omit from the ticker, tracked as future scope** (a real external breadth feed would need its own separate proposal, not bundled into this presentation milestone).
- **Overall "Market Health" score**: found the existing Market Intelligence gauge has *always* shown a hardcoded `0/100` — but investigating further, there is no real aggregate 0-100 score anywhere in ATHENA to plug into it (`MarketHealthAssessment` only has 4 categorical dimension labels — Breadth/Trend Quality/Momentum/Volatility — no scalar score). Synthesizing one would be new business logic. **Decision: omit from the ticker, drop the fake gauge, tracked as future scope** (rather than fabricate a formula or leave the known-broken stub).
- NIFTY 50, BANK NIFTY, and India VIX, by contrast, are all genuinely real: Kite's live snapshot already fetches all three, and daily candles are already ingested for all three too — enough to compute a real day-change % from already-persisted data, not a new calculation.

| | |
|---|---|
| Scope | **Backend** (new, small, additive — Priority-2 exception per the owner's own rule: expose already-computed data, no new provider/architecture/business logic): `MarketTickerDTO`/`MarketIndexTickerDTO` (`dtos/market.py`); `MarketHistoryService.market_ticker()` — reads the latest persisted `MarketSnapshot` + `list_candles_recent()` for the prior close, derives change % via simple arithmetic; `GET /api/v1/market/ticker` (READ). **Frontend**: header ticker markup (shown/fetched only on Decisions & Trace — the one approved new API call), auto-refreshed every 60s while that tab is active (owner-requested refinement — see below); `renderSidebarQuickSummary()` expanded with R:R Potential, Expected Return (reuses the existing `computeExpectedReturnPct`), and Historical Analogs' Win Rate/Avg Holding (explicitly labeled "(Historical)" — there is no forward-looking per-decision holding field anywhere in ATHENA, so this is honestly a past-trades average, not a guarantee), restructured as its own standalone card (owner reference-mock refinement — see below); hero header spacing/hierarchy CSS polish (larger symbol text, clearer grouping divider) — same elements, same data, nothing moved |
| Tests | 4 new backend tests (`test_market_history.py`, including 2 using a real `SqliteRepository` to exercise the actual snapshot+candle-derived arithmetic, one confirming `change_pct` is honestly `None` — never fabricated — without a prior close), plus 2 existing analog-aggregate tests (`test_core_apis.py`) extended with real min/max holding-day assertions. ~35 new dashboard-hosting assertions. Full suite **1035 passed** |
| Coverage | Live-browser verified: ticker shows/hides correctly per active tab (confirmed via real nav clicks, not synthetic pokes); graceful "—" fallback confirmed when the ticker endpoint 401s (no owner credentials for a real authenticated fetch); Quick Summary card visually confirmed via injected sample data — layout matches the reference mock |
| Status | ✅ Approved (2026-07-27) |

**Refinements from owner screenshot review (2026-07-27), before final approval:**

- **Quick Summary → standalone card.** Originally expanded in place at the top of the Reasoning Trace card with no visual separation. Owner shared the reference mock's own Quick Summary treatment (a distinct bordered card, own header + stance badge) and asked for the same. Restructured: `#quick-summary-card` is now its own `.card` sitting above the Reasoning Trace card in `.dag-column` (which now sizes the two cards via flex — Quick Summary sizes to content, Reasoning Trace fills the rest). Header (icon + title + stance badge) lives in static HTML; JS only toggles visibility and the badge's text/class. One deliberate deviation from the mock: the mock's card showed "Holding Period: 2-5 Days" — checked, and no such range field exists anywhere in ATHENA (only a real historical *average*, `avg_holding_days`). Kept the honest "Avg Holding (Historical)" label instead of inventing a range to match the mock exactly.
- **Ticker auto-refresh.** Owner asked how often the ticker refreshes; answer was "never automatically" — no `setInterval` exists anywhere in this dashboard, every tab (including this one) only reloads on tab-switch or a manual refresh click. Owner asked for a timer. Added `startTickerRefresh()`/`stopTickerRefresh()` (60s interval), started when Decisions & Trace becomes active and stopped when leaving it — mirrors the existing `stopOpsStream()` start/stop lifecycle already used for the Operations tab's live stream. Deliberately scoped to the ticker only, not the decisions list/briefing (re-fetching those every tick would reset scroll position/selection, which wasn't asked for).
- **Quick Summary value formatting/coloring** (owner reference-mock screenshot, second review pass): Score and Confidence were showing band words ("Strong"/"HIGH") instead of raw numbers — changed to `75.1/100` and `93.7%` respectively. Risk was showing only the band word — changed to `Medium (42.9)`, colored by band (`tone-good-text`/`tone-warn-text`/`tone-bad-text`, the same utility classes the header ticker's positive/negative colors already use). R:R Potential was `2.00 : 1` (via the shared `formatDecisionRatio`, 2 decimals) — changed to one decimal (`2.0 : 1`) to match the hero cockpit gauge's own "EXPECTED R:R" formatting instead. Expected Return gained sign-based coloring (green/red). All values still come from the exact same `analysisPresentation`/`riskBand` computations the hero gauges already use — only presentation changed, no new number anywhere.
- **Holding Period (real range, not the mock's fabricated one).** Owner asked whether ATHENA can provide a real "Holding Period" in days like the mock's "2 - 5 Days". Checked: each returned analog already carries its own real `outcome_holding_days` (derived from a persisted trade's actual entry-to-exit time), and `DecisionsService._aggregate_analog_outcomes` was already collecting all of them in memory — just to average, never exposing the min/max. Added `min_holding_days`/`max_holding_days` to `DecisionAnalogsDTO`, computed from that same already-collected list (Priority 1/2 — no new provider, no new business logic, exposing more of an existing computation). Quick Summary's "Avg Holding (Historical)" row replaced with "Holding Period (Historical): 3 - 7 Days" (whole-day range across real analogs; collapses to one number if every analog held for the same length of time) — a genuinely real historical range, not a guess.

---

#### DT-3 — Tab restructuring (5 tabs) + spacing polish

Per the earlier owner-confirmed scope decision: split the old single "Decision History" tab into **Response** (Journal/Outcome only) and **History** (Decision Timeline + Similar past setups). No content deleted or invented anywhere — the same three sections (Journal, Decision Timeline, Analogs) were regrouped, not changed.

| | |
|---|---|
| Scope | **Frontend only** (pure presentation regrouping, no backend change): tabstrip button split (`index.html`) — "Decision History" → "Response" + "History", new `fa-clock-rotate-left` icon for History; `renderDecisionBrief()` template (`13-decision-brief-core.js`) — Decision Timeline moved out of the always-visible hero section (it was rendering on every tab, not just when reviewing history — a real instance of "vertical wasted space" per the owner's original assignment) into the new History tabpane; "Similar past setups" (Analogs panel) moved out of the Response tabpane into History, leaving Response with only the Journal/Outcome panel; `BRIEF_TAB_NAMES`/`BRIEF_TAB_LABELS` (`18-decision-brief-trace.js`) extended with `history` → "History". `STAGE_TAB_MAP` unchanged — no DAG stage currently maps to the response/history tabs. |
| Tests | ~35 new/updated dashboard-hosting assertions across all three rounds, plus 7 new backend tests (3 `instruments.name` roundtrip/migration tests including one that simulates a pre-migration db, 1 Kite-dump `name`-column parsing test, 3 `DecisionMetadataDTO.instrument_name` tests via an isolated `tmp_path` repo). Full suite **1042 passed** |
| Coverage | Live-browser verified: all 5 tabstrip buttons present in the correct order (`Trade Plan/Analysis/Market Context/Response/History`) with the correct labels; clicking the History tab correctly activates it (`switchBriefTab`); zero uncaught console errors beyond the expected unauthenticated-fetch logging. Full tabpane content (Timeline+Analogs actually rendering together under History) verified via the source-slice structural test — no live decision could be exercised end-to-end without owner credentials, same constraint as prior milestones. |
| Status | ✅ Approved (2026-07-27) |

**Spacing polish**: the concrete, high-value part of this — removing Decision Timeline from the always-visible hero — already shrinks the hero on every tab except History, directly addressing the original assignment's "Remove Vertical Wasted Space" principle. Did not speculatively tweak further CSS spacing without a concrete target (Trade Plan/Analysis/Market Context tabs were not touched) — per the established pattern this session (DT-1's filter-popover fixes, DT-2's formatting fixes), further spacing polish is best driven by the owner's own screenshot review of the live 5-tab layout, not guessed at.

**Refinement from owner screenshot review (2026-07-27), before final approval:** the owner shared the reference mock's own hero hierarchy (Recommendation+gauges card → collapsed Summary card with "View Details" → tab strip) against the live build, and asked for the same — the full Executive Summary bullet list ("Passed all 6 safety gates.", "composite 65.69 = weighted mean...", etc.) was still always-visible on every tab (same class of issue DT-3 had just fixed for Decision Timeline), and the ATHENA Recommendation banner sat below the tab strip/action bar instead of merged with the gauges above it.

- **Recommendation merged into the gauges row** as its own tile (stance badge + a qualifier band reusing the Score tile's own already-computed word, e.g. "Good Setup" — never a second, independently-derived label). Confirmed with the owner first: skip an "Expected Holding" gauge (same no-real-forward-looking-estimate conclusion as DT-2's Quick Summary), and leave the action bar's position unchanged.
- **Executive Summary collapsed into an "ATHENA Summary" card** — the same real one-line headline previously shown as the banner's reason text, plus a "View Details" button — sitting between the gauges row and the tab strip (matching the mock), instead of a permanently-visible bullet list repeating across every tab.
- **"View Details" opens the full bullet breakdown in a modal**, reusing the exact existing `openModal`/`closeModal` pattern already used for Compare/Chart/Backtest (Priority 1 — no new modal architecture), wired into the global Escape-key/`closeAllModals()` handling.
- The now-empty `.decision-brief-hero` wrapper (Banner + Executive Summary — Decision Timeline had already moved to the History tab earlier in this same milestone) was removed entirely from the per-decision render template; its dead CSS rule was deleted too.
- No backend touched, no content invented — same real headline, same real bullet computations, only repositioned and collapsed behind a click.

**Fix pass (same review):** the Recommendation tile initially shipped as a small stance-chip pill inside a plain dark tile — the owner pointed out the reference mock treats it as a fully stance-tinted highlight card (BUY in large bold green text, tinted green background), not just another gauge tile with a badge. Fixed: `.brief-gauge-recommendation` now takes the same `.stance-buy/-sell/-hold/-pass/-wait` class already used by `.decision-banner` and gets the identical radial-gradient tint treatment; the stance text itself reuses `.hero-metric-band` (same large-bold sizing as Score/Confidence/Risk's own band words) colored per stance, instead of a small `.stance-chip` pill.

**Identity row redesign (owner reference-mock screenshot, third review round):** the top identity row (crosshair icon + ticker + BUY/TRADE badges) redesigned to match the mock — star favorite toggle, company name, "EXCHANGE: SYMBOL" meta row, secondary actions consolidated into a "more" menu.

Researched every new element before building anything, per the Data Source Priority rule:

- **Company full name** ("Dixon Technologies (India) Ltd") — genuine gap, but a *fixable* one: Kite Connect's real instrument dump has always carried a `name` column, ATHENA's ingestion just discarded it. Owner approved the small ingestion change. Implemented: `Instrument.name` (domain model), `SCHEMA_VERSION` 8→9 with an idempotent `ALTER TABLE instruments ADD COLUMN name TEXT` migration (checked via `PRAGMA table_info`, so it safely reaches the *existing* production `db/athena.db` — `CREATE TABLE IF NOT EXISTS` alone is a no-op against an already-existing table), `kite_provider.py`/`file_provider.py` now read/store it, `DecisionMetadataDTO.instrument_name` looked up via a new optional `repo` on `DecisionsService` (same optional-repo-alongside-primary-abstraction precedent as `MarketHistoryService`). **Caveat surfaced to the owner**: the migration already ran against the real db (via the test suite's own real-db wiring) — 506 existing instruments preserved, `name` column added, all correctly `NULL` (never fabricated) since ingestion hasn't re-synced yet; real names populate automatically on the next Kite catalog refresh.
- **Sector** ("Consumer Durables") and **market-cap category** ("Smallcap") — genuine gaps with no fix available: nothing in ATHENA's domain model, database, or Kite's own instrument feed maps a symbol to either. **Owner decision: omit both, tracked as future scope** — the meta row gracefully holds just the one real pill ("NSE: DIXON") today and can take more later without a layout change.
- **Star favorite toggle** — reuses the existing "Saved Symbols" watch-list feature (UX-9b: `GET/POST/DELETE /api/v1/saved-symbols`), previously only a text-input list on Market Intelligence — Priority-2, no new backend, just a new UI surface with a local `Set` cache to avoid re-fetching on every selection.
- **BUY/TRADE badges dropped** from this row (owner-confirmed) — redundant with the Recommendation tile now shown prominently in the gauges row below.
- **Secondary actions moved into a "more" (⋮) popover** — Dismiss today/Remove candidate/Export/News (owner-confirmed which ones); Market Intelligence/Open Chart/Compare stay in the primary action bar. The moved buttons are the exact same elements (ids/classes/click handlers) relocated, not rebuilt — same toggle/backdrop-click/Escape pattern already established for the symbols filter popover.
- **Fix pass (same review):** the ticker ("DIXON") was rendering truncated to "DI…" once the company name sat next to it — flexbox was shrinking both siblings by default since neither had an explicit `flex-shrink`. Fixed: `.decision-brief-symbol-lg` gets `flex-shrink: 0` (the primary identifier must never lose space), `.decision-brief-company-name` is the one that truncates when space is tight.

**Second fix pass (owner live-session screenshots, same day):**

- **Confirmed company name is real and working**: the owner added a new symbol ("ETERNAL") and its real Kite-supplied name ("ETERNAL - ZOMATO" — the stock's actual post-rebrand name) rendered correctly. Investigated why *existing* symbols still showed no name: every scheduled cycle since restart (`--with-cycles`, 60s interval) has been failing at the exact point the instrument catalog gets rebuilt, due to a pre-existing (not introduced this session) invalid symbol `INFSDFSD` in `owner_candidates` (added 2026-07-26, doesn't exist on Kite) — `_ensure_catalog()` raises before any instrument upsert can run, so the catalog (and names) never re-syncs via the scheduler. New/re-validated symbols go through a different, unblocked path, which is why they picked up real names immediately. Flagged to the owner as a separate, pre-existing operational issue — not something fixed as part of this UI request.
- **Market Intelligence button removed entirely** from the identity row's actions — redundant with the sidebar's own "Market Intelligence" nav item, which already does the same `switchTab("market")`.
- **Open Chart / Compare relocated as icon-only buttons** next to Re-validate, in the sticky header-actions row — owner: "icons are also sufficient for these two." Same ids/click handlers, only the container/label changed. With all 3 action-bar buttons removed/relocated, `.decision-brief-actionbar` itself (HTML, JS refs, and CSS) was removed entirely — a further real vertical-space win, not just a relabeling.
- **Fix pass: "Expected R:R" tile text truncation.** With the Recommendation tile added earlier, 5 tiles sit in a 4-column grid — Expected R:R wraps alone onto row 2 but only got 1 of 4 columns' width there, truncating "reward per ₹1 risked" with empty space sitting right next to it. Fixed: `.decision-brief-gauges .brief-gauge:last-child { grid-column: 1 / -1; }` — it's always the last tile, so it now spans the full row.

**Third fix pass (owner live-session screenshot, same day):** company name was truncating on the identity row itself ("SANDHA…") — cramped next to the star toggle, ticker, as-of text, and the newly-added icon buttons, all competing for space in the center column's narrower width. Moved `#decision-brief-company-name` out of the identity row into the meta row (alongside "NSE: SANDHAR"), which has far more width to itself — confirmed via `scrollWidth === clientWidth` (no overflow) that "Sandhar Technologies Limited" now renders in full.

Re-confirmed sector/market-cap category are genuine gaps (re-checked `Instrument`, config, and Kite's exact dump columns a second time — nothing new). **Owner decision (reconfirmed): leave omitted, track as future scope** unless a real external source is identified later.

**Fourth fix pass — Symbols panel color system (owner-requested, same day), three iterations:**

1. Section headers (Trade/Watch/No trade/…) had no background at all — flush with the rows below, indistinguishable from each other.
2. First attempt: reused each section's raw alert-style `dot` color (`--success`/`--warning`) as a `color-mix()` full-block background tint — but those hues are calibrated for a tiny 8px dot, not a background: pure yellow (Watch) visually overpowered green (Trade) at the identical opacity, an imbalance the owner caught immediately on review.
3. Second attempt: balanced the hues with per-section hand-calibrated `tint`/`tintBorder` rgba — but even balanced, 3-4 stacked full-width solid color blocks read as "too much color" overall (owner: "so much of green, so much of yellow, so much of grey").
4. **Final fix**: switched from a full-block fill to a thin left-border accent + a barely-there background wash (`accent`/`wash` fields on `DECISION_CAROUSEL_SECTIONS` in `12-decisions-list.js`) — the same restrained pattern the Recommendation tile/ATHENA Summary card already use elsewhere. The owner's *next* screenshot then pointed at a related, pre-existing (not introduced this session) issue: individual `.symbol-row` rows already had a fully-opaque 3px left border using the same raw `--success`/`--warning` tokens via `decisionCardStanceColor()` — loud cumulatively across a dozen+ stacked rows. Fixed with the exact same muted `accent` rgba values as the headers, so the whole panel now shares one calibrated color system (header accent = row accent per section) instead of two independent, differently-intense color schemes. Hover state uses `filter: brightness(1.25)` (works against any inline background, no per-hue hover color needed).

**Fifth fix pass — individual row accent removed entirely, then divider added (owner-requested, same day):**

- Owner: "im not feeling good with this ui, can we remove opaque 3px left edge line from each symbol card as already we have it in the section header?" — not a further muting pass, a full removal: the section header already carries the color, so the row itself doesn't need to repeat it. `decisionCardStanceColor()` removed entirely (dead code, zero remaining callers checked), the `row.style.setProperty("--stance-color", ...)` wiring removed from `renderSymbolRow`, `.symbol-row` CSS changed to `border-left: 3px solid transparent` (width kept only to avoid a layout jump on `.active`, color gone).
- Owner: "and also remove the left edge 3px border for the selected symbol as well" — `.symbol-row.active`'s `border-left-color`/`border-left-width` overrides removed too; selection now reads entirely from the existing background gradient + full border-color + box-shadow glow, no left-edge accent anywhere in the panel.
- Owner: "this looks good but need subtle divider between symbols" — added `.symbol-row:not(:last-child) { border-bottom-color: var(--border-color); }`, reusing the existing `--border-color` token (no new color introduced).

---

#### DT-4 — Reasoning Trace vertical pipeline list + Similar Trades sparkline

**Part 1 — Reasoning Trace redesign.** Replaced the CSS auto-fit grid + JS-computed SVG connector lines (`drawDAGLines()`, using `ResizeObserver` + `getBoundingClientRect()` to draw `<line>` elements between card-style nodes — fragile once stages wrapped onto a second grid row) with a vertical stepper/timeline list: each stage is a horizontal row (circular icon-wrap + name/status body) connected by a pure-CSS rail (`.dag-node-rail::after`, a `2px` `var(--border-color)` line spanning to the next node) — no coordinate math, immune to wrapping. Same stage order, same click → `selectNode`/`showStageDetails` behavior, same status badge classes (`.meaning-good/-bad/-warn/-neutral`, `.completed/.passed/.failed`) — only the connective visual layer changed.

**Part 2 — Similar Trades sparkline.** Added a compact bar sparkline to the existing "Historical validation" card in the Analogs panel, showing the last 5 similar trades' realized returns. Built entirely from data each analog already carries (`DecisionAnalogDTO.outcome_return_pct`/`outcome_closed_ts`, already fetched by `loadDecisionAnalogs` into `activeAnalogs`) — no new endpoint, no new calculation, per the owner's earlier-confirmed "add the mini sparkline (Recommended)" decision. `analogSparklinePoints()` filters analogs with a realized outcome, sorts by close time, takes the 5 most recent, and orders them oldest-to-newest for a left-to-right trend read; `renderAnalogSparkline()` renders them as an inline SVG bar chart (height proportional to `|return|`, green/red by sign, reusing the same `--tone-good-text`/`--tone-bad-text` tokens the rest of the app already uses for pnl coloring) with a per-bar tooltip (`<title>`) showing the exact date and return %.

| | |
|---|---|
| Scope | **Frontend only** (no backend/DTO change — `outcome_return_pct` already existed on `DecisionAnalogDTO` from an earlier milestone, just unused until now). `18-decision-brief-trace.js`: `renderTraceDAG()` rewritten to build `.dag-node`/`.dag-node-rail`/`.dag-node-icon-wrap`/`.dag-node-body` markup; `drawDAGLines()` and its `ResizeObserver`/`setTimeout` callers removed entirely (dead code, zero remaining callers checked). `index.html`: `<svg id="dag-svg-lines">` removed. `12-decision-cards-dag.css`: `.dag-nodes-flow` grid → flex-column; new `.dag-node`/`.dag-node-rail`/`.dag-node-icon-wrap`/`.dag-node-body` rules; `.dag-svg-overlay`/`.dag-flow-line`/`.dag-flow-line-active`/`@keyframes dag-flow-dash` removed. `19-decision-brief-history.js`: `analogSparklinePoints()`/`renderAnalogSparkline()` added, called from `renderHistoricalValidation()`. `13-context-history.css`: `.analog-sparkline`/`.analog-sparkline-svg`/`.analog-sparkline-bar` (`.tone-good/-bad/-neutral`)/`.analog-sparkline-zero` added. |
| Tests | ~15 new/updated dashboard-hosting assertions (SVG/ResizeObserver artifacts confirmed gone, new `.dag-node-rail`/`.dag-node-icon-wrap`/`.dag-node-body` structure confirmed both in CSS and inside `renderTraceDAG`'s own function body via a source-slice check; `renderAnalogSparkline`/`analogSparklinePoints` confirmed present and wired into `renderHistoricalValidation` via the same source-slice technique). One caught-and-fixed test regression: an explanatory code comment containing the literal word "ResizeObserver" tripped the `not in js` assertion — narrowed to check for `new ResizeObserver` (actual instantiation) instead of the bare word. Full suite **1042 passed**. |
| Coverage | Live-browser verified both pieces via injected sample data (no owner credentials available for a real authenticated load, same constraint as prior milestones): pipeline list renders with the connecting rail, clicking a node sets the active state (accent-colored icon ring + glow + highlighted row background); sparkline renders bars scaled by return magnitude, colored green/red by sign. One rendering snag caught and resolved during verification: the browser had cached the *inner* `@import`-ed CSS file from before this milestone's edit (the outer `dashboard.css` link carries a cache-bust query param, but individual `css/*.css` imports don't) — a cache-bypassing fetch confirmed the new CSS rules were correctly on disk and would apply on a real hard-reload; not a code defect. Zero uncaught console errors from the new code (only the expected unauthenticated-fetch logging already present in every prior milestone's verification). |
| Status | ✅ Approved (2026-07-27) |

---

### PROPOSAL — Scoring differentiation & unwired engine inputs (owner-reported, 2026-07-29)

**Status: proposal only. No code written. Awaiting owner approval before any implementation.**

Owner report: "values like score, risk, confidence are same for all the
symbols until unless i click re-validate." Audited against the live
`db/athena.db`, batch run `run-refresh-20260729T091348-73723088`
(363 symbols). **The report is correct, and it is a backend data defect,
not a UI defect.**

#### Audit evidence

Persistence and the API read path are healthy: all 363 decisions resolve
to their own `decision_reports[decision_id]` entry, so the 2026-07-26
run_id-collision class of bug is **not** recurring here. The frontend is
also clear — `selectBriefing` nulls `activeDepth` and `loadDecisionDepth`
carries a correct `activeDecisionId !== decisionId` race guard. The
persisted values themselves are genuinely near-identical:

| Metric | Distinct values across 363 symbols |
|---|---|
| `risk.overall` | **2** — 328 symbols at 45.67, 35 at 61.67 |
| `confidence.overall` | 10 |
| `score.composite` | 21 |

Risk's degeneracy is mathematically forced, and was verified as an exact
1:1 mapping: of its six dimensions, two are permanently UNKNOWN
(`event_risk`, `concentration_indicator`), three are identical for every
symbol because they derive from index-wide regime/market health
(`volatility_risk` 50, `gap_risk` 70, `market_environment_risk` 48.75),
and exactly one varies (`liquidity_risk`, a binary 20-or-80 volume
threshold). One binary input can only produce two outcomes. Confidence
degenerates the same way: three constant dimensions, one permanently
UNKNOWN (`data_freshness`), and only `cross_engine_agreement` and
`consistency` moving.

Re-validate does not correct anything — it re-runs one symbol at a newer
timestamp against fresher intraday data, so that symbol may cross a band
boundary and merely *look* distinct. Observed: ZEEL scored 65.00 in the
09:13 batch and 63.24 when re-validated at 09:31.

#### Root cause: three engine inputs that are accepted but never passed

| # | Engine parameter | Original consequence | Current status |
|---|---|---|---|
| D-1 | `RiskEngine.assess(calendar_context=...)` | `event_risk` permanently UNKNOWN | ✅ Closed — `CalendarContext` now threaded from `OwnerValidationPipeline.run()` |
| D-2 | `RiskEngine.assess(universe=...)` | `concentration_indicator` permanently UNKNOWN | ✅ Closed — `UniverseResult` now threaded, with scoped re-validate fix using last full-cycle breadth |
| D-3 | `ScoringEngine.score(sector_health=...)` | `sector_quality` (**weight 15 of 100**) permanently UNKNOWN for every symbol ever scored — every report shows `completeness: 0.85` | ⏳ Blocked — see sector data decision below |

D-1 and D-2 are now closed. `OwnerValidationPipeline.run()` threads the
existing `CalendarContext` and `UniverseResult` into `_scan_eligible()`,
which passes them into `RiskEngine.assess()`. The follow-up scoped
re-validate bug is also fixed: scoped runs use the last real full-cycle
universe breadth for `concentration_indicator`, and regime/gap context
uses real configured index candles instead of falling back to an
arbitrary stock. No new data source, no contract change.

**D-3 is blocked on data, not on wiring.** `SectorHealthEngine` was built
and approved under M2.3 and `config/sector_health.json` exists, but its
trend/momentum/volatility dimensions consume a *sector index* candle
series, and the repository holds candles for only three non-equity
instruments: `NSE:NIFTY 50`, `NSE:NIFTY BANK`, `NSE:INDIA VIX`. No
sector indices (NIFTY IT, NIFTY PHARMA, …) are ingested. Sector
*metadata* is present and good (`instruments.sector`, 15+ sectors, only
10 nulls), so a constituent-derived sector aggregate is feasible — but
that is a new computation method, not the approved M2.3 engine, and
would need its own design decision.

#### Expected impact of enabling `sector_quality` — this is the risk

Because the composite is a weighted mean over *known* components only,
enabling a weight-15 dimension rescales every score in the system:
`new = 0.85 × current + 0.15 × sector_value`. Modelled against the 363
live decisions (current mix: TRADE 159, WATCH 167, NO_TRADE 37):

| Sector value | Resulting mix | Symbols whose decision changes |
|---|---|---|
| 20 (weak sector) | TRADE 70, WATCH 203, NO_TRADE 90 | **142 / 363 (39.1%)** |
| 50 (mixed sector) | TRADE 149, WATCH 177, NO_TRADE 37 | 10 / 363 (2.8%) |
| 80 (strong sector) | TRADE 203, WATCH 155, NO_TRADE 5 | 76 / 363 (20.9%) |

**218 of 363 symbols (60.1%) would have their TRADE/WATCH/NO_TRADE band
determined by their sector score alone.** This is not a cosmetic change
and must not ship without owner sign-off on the recalibration.

#### Proposed milestones (small, independently reviewable)

| Milestone | Scope | Gate | Status |
|---|---|---|---|
| **SD-1** Wire calendar + universe into Risk | Thread the existing `CalendarContext` and `UniverseResult` from `run()` into `_scan_eligible()` → `RiskEngine.assess()`. Activates `event_risk` and `concentration_indicator`. Includes the approved follow-up fix for scoped re-validations: use last full-cycle breadth for concentration and real configured index candles for regime/gap context. Note: `concentration_indicator` is universe-breadth-derived and therefore shared across symbols — it raises risk *completeness* and honesty, it does **not** add per-symbol differentiation. Only `event_risk` can vary per symbol, and only on instruments with calendar events | None — existing objects, existing parameters, no contract/schema change | ✅ Completed / approved (2026-07-29) |
| **SD-2** Sector health data decision | Owner decision, not an AI call: either (a) ingest real NSE sector indices via Kite (new data source → **DD-gated**), or (b) derive sector aggregates from the constituent candles already held, using `instruments.sector` (new method → needs a design decision / ADR since M2.3's engine contract assumes an index series) | **DD or ADR** depending on option chosen | ✅ Approved — Option A implemented ([`DD-12`](decisions/DD-12-sector-health-data-source.md), 2026-08-01) |
| **SD-3** Wire sector_quality + recalibrate thresholds | Only after SD-2 lands. Pass `sector_health` into `ScoringEngine.score()`, then re-tune `config/decision.json` watch/trade thresholds against the impact table above so the change doesn't silently reclassify 20–39% of the book. Ships with a before/after replay diff | Config change to decision thresholds — **owner approval required** | 🔄 **Wiring done under ID-P0 (2026-08-29, not SD-3 itself)**; **real measured replay impact done under ID-P0.1 (2026-08-29)** — see the note immediately below. Threshold recalibration remains separately proposed and un-started |
| **SD-4** Scoring granularity (continuous ramps) | Replace RSI/liquidity/ADX step functions with anchor-preserving linear ramps. Distinct composite scores rise from 21 → 248 across the live book. `technical_structure` deferred (needs a normalizing band with no existing anchor). | Config: `adx.weak`, `liquidity.low_volume_floor_ratio` | ✅ Completed / approved (2026-07-29) |

**SD-3 status note (updated 2026-08-29, ID-P0.1):** ID-P0 (the Intraday
Intelligence program's prerequisite architecture milestone) wired
`sector_health` into `ScoringEngine.score()`,
`EvidenceAggregationEngine.aggregate()`, and `DecisionEngine.decide()` per
an explicit, current owner instruction that also explicitly forbade
tuning any threshold as part of that change ("this is expected behavior,
but it must be made explicit... do NOT tune any thresholds based on
changed composites"). **This is only the wiring half of what SD-3
originally scoped as one gated milestone** — the impact table above
(modelled: up to 218/363, 60.1%, of one historical book's TRADE/WATCH/
NO_TRADE band could shift with real sector data) was the reason SD-3
bundled recalibration into the same approval gate in the first place.
`config/decision.json`'s watch/trade thresholds remain untouched.

**ID-P0.1 (2026-08-29) has now measured the real effect**, closing the
"has not been run" gap this note originally flagged:
`docs/research/ID-P0.1-SECTOR-WIRING-REPLAY-IMPACT-REPORT.md` — a
deterministic (byte-identical across two independent replay attempts)
comparison of 380 real, currently-eligible instruments from the real
production book, sector-wiring on vs. off, everything else held
structurally identical and verified so. Measured: 15/380 (3.95%)
decisions change type — an order of magnitude below the 60.1% worst-case
model, because real per-sector values vary rather than being uniformly
20/50/80 and only 37.6% of the book has a resolvable sector at all;
composite delta among the 143 affected instruments has mean +0.24/median
−0.04; risk is exactly untouched (0.0 delta, 380/380); confidence moves
too (mean +1.05 among the affected instruments — a real, traced,
legitimate second-order effect of `sector_quality` newly participating in
`ConfidenceEngine`'s cross-engine-agreement/unknown-ratio/consistency
dimensions, not a bug). ID-P0.1's own report also names its limitation
honestly: this is one real snapshot, not a multi-date historical replay,
because `list_candles_recent()` has no point-in-time cutoff — a genuine
multi-session replay would need new point-in-time repository
infrastructure, which was out of scope for a measurement-only checkpoint.
**Recommendation from ID-P0.1: ID-1 READY.** Whether SD-3's threshold
recalibration is still worth pursuing given this smaller-than-modelled
real impact is the owner's call, not decided here.

#### SD-2 — Option A implemented and approved (2026-08-01)

Scope completed, per [`DD-12`](decisions/DD-12-sector-health-data-source.md)
§7: `config/providers/kite.json`'s `index_instruments` extended to the 8
NIFTY sectoral indices IX-1 already tracks; a new, additive
`config/sector_index_mapping.json` + `SectorIndexMappingConfig`
(`src/athena/config/models.py`) explicitly maps 8 of ATHENA's 20
`instruments.sector` values to those indices — deliberately not exhaustive,
never guessed by string similarity; `SectorHealthEngine` (M2.3, approved,
previously never instantiated outside its own tests) now runs every cycle
in `OwnerValidationPipeline` for whichever sectors have a mapped index with
real candle data, persisting real per-sector assessments into
`detail["sector_health"]`; a new `athena backfill-sector-indices` CLI
command (reusing the existing `LiveIngestionEngine`/validator/quarantine
path, not new candle-fetching logic) one-time-backfills history for the 8
indices.

**Scoring/decision were provably untouched at the time this SD-2 entry was
written.** `ScoringEngine.score()`'s only call site (`owner_validation.py`'s
`sco_stage`) did not pass `sector_health` — confirmed by direct code
reading, not inference — so `sector_quality` was exactly `UNKNOWN` for
every symbol at that point. **This changed under ID-P0 (2026-08-29)** — see
the SD-3 status note above; the wiring is now live, threshold
recalibration is not.

Validation note: full suite 1,166 passed (7 new tests covering the new
config models and an end-to-end `OwnerValidationPipeline.run()` check
against the real production `config/` directory, not a copy). Also
live-verified against the real environment: ran the new backfill CLI for
real against Kite — fetched and wrote 504 real daily candles across all 8
sector indices (63 bars each, 2026-05-04 to 2026-07-31), confirmed directly
against the database afterward. Ruff clean (one pre-existing, unrelated
`SizingConfig` redefinition finding, predates this session).

**Correction:** this milestone's own earlier design work (and DD-12's first
draft) claimed the 3 benchmark indices had "925 daily bars" of history to
reuse a backfill mechanism from — that number was a same-session misreading
(summed candle rows across all three timeframes: 1d+5m+15m). The real
benchmark daily history was 67 bars, and no backfill mechanism existed
before this milestone; `athena backfill-sector-indices` is genuinely new
code. See `docs/design/ATHENA-INDEX-SECTOR-INTELLIGENCE-ROADMAP.md`'s own
correction note and DD-12 §7 for the full detail.

#### SD-1 consequence found during implementation: `max_risk_for_trade` was tuned against an incomplete denominator

Modelled against all 363 live decisions with a simulator validated to
reproduce the persisted risk values and TRADE/WATCH/NO_TRADE split
**exactly** (0 mismatches on 363 rows, baseline 153/173/37).

Risk is a weighted mean over *known* dimensions only. With two of six
dimensions permanently UNKNOWN, the divisor was 75 of 100 weight, which
inflated every risk score. Completing the vector adds two genuinely
low-risk inputs (`event_risk` 20 on a normal day, `concentration_indicator`
30 for a diversified universe) and mechanically deflates the result:

| | risk (liquid names) | risk (illiquid names) | RISK gate at max 60 |
|---|---|---|---|
| Before SD-1 | 45.67 | 61.67 | 35 symbols fail |
| After SD-1, normal day | 40.25 | 52.25 | 0 fail |
| After SD-1, expiry | 47.75 | 59.75 | 0 fail |
| After SD-1, scheduled events | 49.25 | 61.25 | 35 fail |

**The `max_risk_for_trade: 60` threshold was implicitly calibrated
against the incomplete 4-dimension scale.** Shipping the wiring alone
therefore silently *loosens* the trade gate: 6 symbols flip WATCH → TRADE
(AIIL, APLAPOLLO, CREDITACC, JSL, LALPATHLAB, MANKIND) — all of them
names whose 20-week volume sits just under the 500k liquidity floor
(CREDITACC is 485,186, a 3% shortfall). These would become live BUY
setups on the least liquid stocks in the book.

Strictness-preserving recalibration: **`max_risk_for_trade: 60 → 50`**
reproduces today's exact pass/fail partition across all three calendar
scenarios (40.25/47.75/49.25 pass; 52.25/59.75/61.25 fail). Owner
approved this risk-appetite choice and the live config now uses 50.

#### SD-4 — continuous scoring (design approved, implemented 2026-07-29)

Even with all three inputs wired, per-symbol differentiation stays
chunky, because `config/scoring.json` collapses continuous signals into
a handful of fixed buckets:

| Component | Weight | Current mapping | Distinct values observed |
|---|---|---|---|
| `momentum` | 20 | RSI → 3 buckets at thresholds 40 / 60 (20 / 50 / 80 pts) | 3 |
| `liquidity` | 10 | Volume MA vs a single 500k threshold (30 / 70 pts) | 2 |
| `technical_structure` | 15 | Above/below MA (30 / 70) + fixed MACD bonus 10 | 4 |
| `trend` | 20 | Index regime label + fixed ADX>25 bonus 10 | 2 |
| `market_quality` | 20 | Index-wide — **identical for all 363 symbols** (51.25) | 1 |

A symbol at RSI 40.1 and one at RSI 59.9 receive the exact same 50
momentum points, and a symbol at RSI 59.9 versus 60.1 jumps a full 30
points on a rounding-width difference — the bands are simultaneously too
flat inside and too cliff-edged at the boundary.

**Approved design (implemented 2026-07-29).** Replace the step functions
with linear ramps that pass exactly through the anchor values already in
`config/scoring.json`, so this is a strict refinement of the existing
calibration rather than a re-weighting:

- **momentum** — `pts = 20 + 3 × (RSI − 40)`, clamped to `[20, 80]`.
  This reproduces all three configured anchors exactly: RSI 40 → 20
  (`weak_points`), RSI 50 → 50 (`mid_points`), RSI 60 → 80
  (`strong_points`). **No new config field required.**
- **liquidity** — ramp the volume ratio `vma / min_volume_ma` from 0.5×
  to 1.0× across `low_points` → `ok_points` (30 → 70), preserving the
  anchor at exactly 1.0× → 70. Requires **one new config field** for the
  lower ratio bound (proposed `low_volume_floor_ratio: 0.5`).
- **trend (ADX bonus)** — ramp `0 → bonus` across ADX 15 → 25 instead of
  a binary switch at 25, preserving the anchor at ADX 25 → full bonus.
  Requires one new config field for the lower bound.
- **technical_structure** — deferred. Making MA distance continuous needs
  a normalizing band (likely ATR-relative) that has no existing anchor to
  preserve, so it is a genuine calibration decision rather than a
  refinement. Left discrete pending its own proposal.

**Replayed against all 363 live decisions** (momentum + liquidity ramps):

| | current | proposed |
|---|---|---|
| distinct momentum values | 3 | **232** |
| distinct liquidity values | 2 | **34** |
| distinct composite scores | 21 | **248** |
| band mix | TRADE 159 / WATCH 167 / NO_TRADE 37 | TRADE 159 / WATCH 149 / NO_TRADE 55 |

34 of 363 symbols (9.4%) change band. The direction of travel is
correct in both tails — it penalises names that are genuinely weak but
currently hidden inside the flat mid-band, and rewards genuinely strong
ones:

| Symbol | Input | Current | Proposed | Score |
|---|---|---|---|---|
| NSE:APLAPOLLO | volume MA 497,699 (0.5% under floor) | liquidity 30 | 69.6 | 60.29 → 69.65 |
| NSE:CREDITACC | volume MA 485,186 | liquidity 30 | 67.6 | 69.71 → 74.13 |
| NSE:NTPC | RSI 40.02 (at the weak edge) | momentum 50 | 20.1 | 60.29 → **53.25, drops out of TRADE** |
| NSE:SAILIFE | RSI 59.86 (at the strong edge) | momentum 50 | 79.6 | 58.53 → 67.35 |

NTPC is the clearest illustration: at RSI 40.02 it sits a fifth of a
point above the weak threshold, is currently scored as mid-band, and
clears the trade level on that basis. Under the ramp it scores as what
it is — barely-not-weak — and correctly falls out of TRADE.

Owner approval was required because this changes 9.4% of decisions and
adds two config fields; approval was received before implementation.

**Implemented and approved 2026-07-29**: `_linear_ramp` in
`scoring/engine.py`; `adx.weak: 15.0` and `liquidity.low_volume_floor_ratio:
0.5` added to config + models; RSI `mid_points` validated as the honest
mid-band anchor on the continuous ramp. Six new anchor/ramp regression
tests in `tests/decision/test_scoring.py`. Full suite 1107 passed at the
time of implementation; focused SD regression tests currently pass.

---

#### Migration / re-validation plan (applies to SD-3 and SD-4)

Any change to scoring output makes every already-persisted decision
non-comparable with new ones. SD-4 is now implemented, so operational
use should start from a clean book: take a repository backup via the
existing backup path, use the existing "Clear all" admin utility, then
run a fresh full validation. Apply the same clean-slate approach when
SD-3 eventually lands, because sector-quality wiring will also change
score comparability.

#### Incidental finding (not the reported bug, not fixed)

`loadDecisionDepth`'s catch block calls `renderDecisionDepth(null)` but
not `renderSidebarQuickSummary()`, so a depth-load *failure* can leave
the right-rail quick summary showing the previously selected symbol's
numbers. Not the cause of the owner's report (all 363 depth loads
resolve successfully), but worth folding into whichever milestone
touches this file next.

---

#### Fix pass: scoped re-validate inflated risk via concentration_indicator (owner-reported, 2026-07-29)

Owner: "im seeing risk value of 31.3 for most of the symbols which are
exist in the decision list... if i re-validate again, then the risk
value changes." Two distinct findings:

1. **31.3 for most symbols during a full cycle — by design, not a bug.**
   4 of the Risk Engine's 6 dimensions (`volatility_risk`, `gap_risk`,
   `market_environment_risk`, `concentration_indicator`) are inherently
   market-wide — identical for every symbol scanned in the same cycle by
   design (they measure market conditions, not stock-specific ones).
   Only `liquidity_risk` genuinely varies per symbol, and it's a coarse
   binary (below/above a volume threshold), so most similarly-liquid
   stocks converge on the same overall weighted risk.
2. **Re-validating changes the value — a real bug, and a gap SD-1 didn't
   catch.** A `symbols_filter`-scoped run (single-symbol Re-validate /
   Add & validate) narrows the universe scan to just that one
   instrument, so `concentration_indicator`'s "eligible instrument count"
   collapses to 1 → always `concentrated_risk` (70, HIGH), regardless of
   real market breadth. Confirmed directly against `db/athena.db`: a
   scoped TCS re-validate showed `concentration indicator 70 (1 eligible
   instruments)` — an artifact of that call's own narrow scope, not of
   the market. SD-1's own before/after modeling assumed the diversified
   (30) case throughout, since it was validated against full-cycle data;
   it never exercised the scoped single-symbol path.

Owner-approved fix: reuse the last real FULL (unscoped) cycle's universe
breadth for concentration purposes when this run is itself scoped, never
fabricate one when no prior full cycle exists yet (ADR-005).

| | |
|---|---|
| Scope | `owner_validation.py`: `detail["universe_scope"]` (`"full"`/`"scoped"`) added to the persisted run detail; new `_last_full_universe_summary()` — scans `list_runs()`/`get_run_detail()` for the most recent COMPLETED/DEGRADED run marked `"full"`, returns its real `universe_summary` wrapped in a new `_UniverseSummaryStandIn` (duck-types `UniverseResult` for `RiskEngine._concentration_indicator`, which only reads `.summary`); `_scan_eligible` computes `concentration_universe` once per call — the scan's own `universe_result` when unscoped, `_last_full_universe_summary()` when `symbols_filter` is set — and `risk_stage` now passes that instead of the raw scoped result. |
| Tests | 2 new regression tests: a scoped re-validate reuses the prior full cycle's real breadth (not its own 1-symbol scope); with no prior full cycle, concentration is honestly `UNKNOWN`, never fabricated. Full suite **1109 passed** |
| Coverage | Verified against real production `db/athena.db`: a scoped TCS re-validate went from `concentration_indicator: 70 (HIGH, "1 eligible instruments")` to `UNKNOWN` (`_last_full_universe_summary()` correctly found no prior run carrying the new marker — honest degradation, not a crash); overall risk dropped from the inflated 42.75 to 39.72, completeness 0.9 (5/6 known). |
| Status | ✅ Fixed, superseded by two follow-ups below |

**Follow-up 1 — the fix above never actually fired in production (owner re-tested, still broken).** `_last_full_universe_summary()` checked `detail.get("universe_scope")` at the top level of a run's persisted `detail_json` — correct for a direct test call, but `DryRunCycleOrchestrator.run_cycle()` (`scheduling/dry_run.py`, the real code path behind both the scheduled cycle and the "Run Full Validation" button) persists this pipeline's own returned dict nested one level down, under a `"pipeline"` key, alongside `"phase"`/`"duration_seconds"`/`"ingestion"`. Every real production run's marker lived at `detail["pipeline"]["universe_scope"]`, which the lookup never checked, so it always fell through to `None` — concentration stayed `UNKNOWN` forever, and its low-risk anchor being dropped from the weighted mean was still inflating individual re-validate risk versus the full cycle. Fixed: `_last_full_universe_summary()` now checks the nested `"pipeline"` shape first, falling back to flat for direct callers (tests). New regression test locks in the real nested shape specifically. Verified against `db/athena.db` after a required server restart: a scoped ZENSARTECH re-validate's `concentration_indicator` went from `70 (HIGH)` to the real full cycle's `30 (LOW, "362 eligible instruments")`.

**Follow-up 2 — a second, deeper bug found while diagnosing the first: `gap_risk` differed between a full cycle and a re-validate even after Follow-up 1, with every other dimension identical.** Root cause, found via direct dimension-by-dimension comparison: `_scan_eligible` resolved its regime-benchmark index as `index_id = next(iter(snapshot.indices.keys()))` — but `MarketSnapshot.indices` keys are bare labels (`"NIFTY 50"`), while the `candles` table stores everything under the full instrument_id (`"NSE:NIFTY 50"`). `self._repo.list_candles_recent("NIFTY 50", ...)` (no prefix) always returned zero rows, so the code fell through to its last-resort fallback — `candles_by_id.get(included_ids[0], ())` — **an arbitrary individual stock's own candles standing in for "the market index."** Which stock won depended entirely on scan scope: the first eligible symbol (alphabetically/whatever order) in a 362-symbol full cycle, versus the target symbol itself in a single-symbol re-validate — silently fabricating a different "market regime" reading every time, the opposite of ADR-005. Confirmed directly: the full cycle's "index candles" showed a price series around ₹1,130 (some unrelated stock); the ZENSARTECH re-validate's showed ₹524–533 (ZENSARTECH's own price) — neither is NIFTY 50 (~24,000).

Fix: new `_resolve_index_candles()` — always tries the configured index instruments (`config/providers/kite.json`'s `index_instruments`, correctly prefixed) in order via the repo, requiring genuine candle history before accepting one; never falls back to an unrelated instrument's own candles. Shared by both `_scan_eligible` and `_maybe_regime` (removing a near-duplicate second copy of this same resolution logic). 2 new regression tests (resolves the real index, not a random stock; honestly empty — not fabricated — when no index data exists at all). Full suite **1112 passed**.

**Final verification (both follow-ups together, real production data, post-restart):** a full cycle and a scoped ZENSARTECH re-validate now produce **identical** risk across all 6 dimensions — `volatility_risk 50, liquidity_risk 20, gap_risk 70, event_risk 20, market_environment_risk 41.25, concentration_indicator 30` — both landing on **overall risk 38.75**. (Note: `gap_risk 70`/GAP_UP is the mathematically correct reading of NIFTY 50's real open-vs-prior-close, 0.75% against a 0.5% threshold — the earlier `NO_GAP` some runs showed was itself wrong, an artifact of the random-stock substitution, not a legitimate alternate reading.)

| | |
|---|---|
| Scope | `owner_validation.py`: `_last_full_universe_summary()` checks the nested `"pipeline"` detail shape; new `_resolve_index_candles()` replacing the broken snapshot-label-based index resolution in both `_scan_eligible` and `_maybe_regime` |
| Tests | 3 new regression tests (nested-shape lookup; real-index-not-random-stock; honest empty with no index data). Full suite **1112 passed** |
| Coverage | Verified against real production `db/athena.db` after each fix, and again with both together: full cycle vs. scoped re-validate now match on every one of the 6 risk dimensions, not just concentration |
| Status | ✅ Fixed (2026-07-29) |

---

---

### Market Intelligence UX track (owner direction, 2026-08-03)

Screenshot-driven audit and correctness/IA pass over the Market Intelligence
dashboard screen. Presentation and information-architecture only; any fix
touching a backend calculation corrects it to be internally consistent, it
does not invent new metrics or policy. Governing plan:
`docs/design/ATHENA-MARKET-INTELLIGENCE-UX-ROADMAP.md`.

| Milestone | Scope | Gate | Status |
|---|---|---|---|
| **MI-UX-0** Design & audit gate | 11 findings across 3 severities from a live screenshot audit; owner sign-off to start with P0 | Owner approval | ✅ Approved (2026-08-03) |
| **MI-UX-1** P0 correctness fixes | Fix Top Opportunities mid-card clipping, Breadth 0%/WEAK vs. ADV/DEC contradiction, Market Health unavailable-tile prominence | Owner review; no fabricated data | ✅ Approved (2026-08-03) |
| **MI-UX-2** Freshness & alert unification | One shared freshness phrasing; real alert treatment for failed runs/blockers | Owner review | ✅ Approved (2026-08-03) |
| **MI-UX-3** Visual consistency & IA | One metric-tile idiom; actionable-first Universe default view; grouped header | Owner review | ✅ Approved (2026-08-03) |
| **MI-UX-4** Polish & release gate | RS label clarity, Quick Actions dedup, Evidence Attribution prominence, full screenshot/regression QA | Owner review after QA evidence | ✅ Approved (2026-08-03) |

**Market Intelligence UX track closed (2026-08-03):** owner approved all four
MI-UX milestones. No known finding from the original 11-item audit remains
open.

**Implementation rule:** one MI-UX milestone at a time. MI-UX must never
create order placement, broker write actions, new signals, or changes to
ATHENA's analytical engines.

#### MI-UX-1 — P0 correctness fixes (ready for review, 2026-08-03)

Scope completed, with one finding corrected and one re-scoped after live
verification against the real database rather than trusting the screenshot
read at face value:

1. **Top Opportunities Today mid-card clipping — confirmed and fixed.** The
   shared, height-constrained summary band could land its clip boundary
   mid-row, rendering later sector cards with a visible header and no visible
   symbol content. `constrainTopOpportunitiesCards()`
   (`js/09-market-intelligence.js`) now measures the grid's own resolved
   column count and each card's real rendered height at render time, caps the
   grid to whole rows only (2 by default), and adds an explicit
   `+N more opportunities — show all` control for the rest — a card now
   either renders completely or not at all, never partially. Verified live
   across three viewport widths (3-column/no cap needed, 2-column/capped with
   correct hidden count, and post-expand/uncapped), including confirming the
   expand control correctly reveals the remainder.
2. **Breadth `0%`/`WEAK` vs. `ADV 384 · DEC 124` — not a real bug, audit
   finding retracted.** Traced `advance_pct`'s construction
   (`market_summary_service.py`) and the real persisted run detail directly:
   `advance_ratio` was `0.7559` (→ "strong", 80 pts), matching the ADV/DEC
   counts exactly. The screenshot read during the audit was mistaken; no code
   changed for this finding.
3. **Market Health "Unavailable" — real root cause found, message enriched.**
   The persisted run detail showed `institutional_strength` component
   `points: null` with its own explanation already computed:
   `"institutional flow session_date 2026-07-22 is stale (age_days=12 >
   max_age_sessions=3)"` — a stale input file, not a structurally missing
   feature. `construct_market_health_score()` (`market_health/score.py`) was
   discarding that specific explanation and returning only "missing required
   component(s): institutional_strength." It now includes each missing
   component's own explanation in `unavailable_reason`, so the tooltip and
   Evidence Attribution line tell the owner *why* and give them something
   actionable (refresh the institutional flow file) instead of an
   unexplained permanent-looking gap. This does not change any score,
   threshold, or classification — only the diagnostic message text, built
   from data the engine already computes.

Architectural note: presentation and message-text only. No score, threshold,
regime, decision, or TradePlan value changed; no broker write action added.

Validation note: full suite **1252 passed**. Live-verified against a
read-only backup of the real database through an isolated local instance
(separate `db/`, separate port, `ATHENA_SINGLE_USER` bypass for this instance
only — the real `.env`/session/port were never touched) rather than against
synthetic data, so the fix is confirmed against genuine persisted run
detail and genuine grid layout behavior.

**Follow-up — the fix above never actually engaged on the owner's real
monitor (owner-reported, 2026-08-03, same day).** The first
`constrainTopOpportunitiesCards()` capped to a flat 2 rows regardless of the
grid's real column count. On the owner's wide monitor all 5 sector cards
resolve to a single grid row (`colCount=5`), so `rowsTotal(1) <= maxRows(2)`
was always true and the function returned immediately without capping
anything — the *outer* `.market-summary-band` boundary (untouched by that
early return) kept cutting straight through that one tall row exactly as
before the fix, reproducing the original bug. Root cause: capping by a
guessed row count instead of the real remaining space in whichever ancestor
actually clips. Fixed by measuring `available` directly from
`cardsEl.closest(".market-summary-band")`'s real remaining boundary and
walking actual per-row card bottoms (no fixed row-height assumption, since a
1-symbol vs. 2-symbol sector card differs in height) to find how many whole
rows genuinely fit — 0 rows is now an honest, valid outcome (clean "+N more"
button, no heading-only guess) rather than forcing a fixed minimum.
Re-verified live at the owner's exact reported layout (5-column single row,
1970×870/1050 viewports): correctly caps to 0 visible rows with an honest
`+5 more opportunities — show all` control; expanding reveals all 5 cards,
each showing genuine symbol content (never a bare header), falling back to
`.market-summary-band`'s own pre-existing scrollbar for the deliberately
user-requested "show everything" state — the same sanctioned fallback the
original MARKET_MAIN_MIN_HEIGHT fix already relied on. Also re-verified the
3-column (no cap needed) and 2-column (mid-size cap) cases still behave
correctly after the rewrite. Full suite re-run: **1252 passed**.

---

#### MI-UX-2 — freshness & alert unification (approved, 2026-08-03)

Scope completed:

1. **One shared freshness phrase.** Market Summary already used "As of";
   Index Leadership ("Observed"), Top Opportunities ("Updated"), and
   Validation Pipeline's funnel footer ("Last Updated:") each had their own
   wording for the identical "this reflects a snapshot taken at this time"
   concept — and, per the original audit, didn't even agree with each other
   in one screenshot. All four now render `As of ${formatDecisionTime(...)}`
   via the same shared `formatDecisionTime()` — the underlying time format
   was already consistent app-wide; only the verb varied. Forward-looking
   text ("Market closed · next live...") was deliberately left as its own
   distinct phrasing — it's a different concept (upcoming schedule, not a
   snapshot), not part of what made the wording inconsistent.
2. **Failed-run alert treatment.** The Validation Pipeline's "Latest ·
   Blocker · next action" strip rendered a FAILED run in the same muted
   register as routine metadata — the single most actionable state on the
   card had no visual priority. Now mirrors the existing
   `.decision-actionability-banner.tone-danger` convention already used
   elsewhere in the app (left-border accent, tinted background, warning
   icon): a failed run turns "Latest" red and gives the next-action line a
   red-bordered, icon-tagged banner instead of plain text.

Architectural note: presentation-only — reuses existing `as_of` fields and
the existing `overall_status` already carried by the loaded run; no new
endpoint, no scoring/decision change.

Validation note: full suite **1257 passed** (one pre-existing regression
test asserted the literal string `"Last Updated:"` and was updated to assert
the new shared phrase instead — a deliberate wording change, not a broken
lock). Live-verified against a read-only backup of the real database through
an isolated local instance: confirmed all four sections now read "As of" in
the same screenshot; confirmed the alert banner (red border, tinted
background, triangle icon) renders correctly for a FAILED latest run and
stays absent for a completed one.

---

#### MI-UX-3 — visual consistency & information architecture (approved, 2026-08-03)

Scope completed:

1. **One metric-tile idiom.** Momentum was the one "bar" shape among three
   Market Summary tiles that all visualize the exact same 0-4 categorical
   level via the shared `renderCategoricalIndicator()` — Trend Quality and
   Volatility Quality were already dots; the split was pure historical
   inconsistency, not a semantic difference. Momentum now renders as a dot
   indicator too. Deliberately left untouched: Regime/Volatility's
   sparklines (they show a real recent trend a static indicator can't) and
   Breadth/Market Health's rings (they're genuine 0-100 percentages) — both
   pairs were already internally consistent with each other and forcing
   them into a third shape would have discarded real information, not
   fixed an inconsistency.
2. **Actionable-first Universe default.** The status filter
   (`#universe-status-filter`, already existed) defaulted to "All
   statuses," so the mostly-Excluded majority dominated the visible list
   ahead of Eligible rows. Now defaults to "Eligible" — "All statuses" and
   "Excluded" remain one click away via the exact same control. No new UI;
   reuses the existing filter/count-chip machinery (`applyUniverseFilters()`
   already runs on load and already shows "N of 511" whenever a filter
   narrows the view).
3. **Grouped header.** Kite/System-Health status pills and the
   diagnostics/refresh/guide/restart action icons sat in one
   undifferentiated `.header-actions` row. Now wrapped into
   `.header-status-group` / `.header-action-group` with a thin divider
   between them — same elements, same ids, same behavior, purely a DOM/CSS
   grouping change.

Architectural note: presentation-only. No score, decision, regime, or
TradePlan value changed; no backend endpoint added or changed. The header
change touches shared markup used by every tab (not just Market
Intelligence), since the header itself is a shared component — grouping it
by status-vs-action is a general improvement, not something that could be
scoped to one tab alone.

Validation note: full suite **1257 passed** (one pre-existing test asserted
the literal string `".market-bar-indicator"` was present in the CSS bundle;
updated to assert it's absent instead, locking in the removal). Live-verified
against a read-only backup of the real database through an isolated local
instance: confirmed Momentum renders dots identical to the other two tiles;
confirmed Universe opens showing "363 of 511," every visible row Eligible,
with the filter-toggle's active-filter indicator correctly lit; confirmed
the header shows Kite + Healthy grouped together, a visible divider, then
the four action icons.

Testing note (verification-environment artifact, not a product bug): this
port had been reused for isolated verification many times earlier in this
session, and the browser had independently cached `dashboard.css`'s
sub-imports (`css/03-shell.css` etc.) from those earlier loads — those
inner `@import` URLs carry no cache-busting query string the way the outer
`dashboard.css?v=9.140.0` does, so a normal reload kept serving stale CSS
even after the HTML itself was freshly fetched. Confirmed via direct `curl`
that the server always had the fresh CSS, and via a manual `fetch()` with
`cache: 'no-store'` that the fresh CSS renders correctly. Suggested
improvement for a future milestone: the `@import`ed `css/*.css` (and
`js/*.js`) sub-resource URLs referenced from `dashboard.css`/`dashboard.js`
carry no cache-buster of their own, unlike the outer files — real users may
need a hard refresh to see a deploy take effect immediately.

---

#### MI-UX-4 — polish & release gate (ready for review, 2026-08-03)

Scope completed — the last 3 findings from the original audit (§2 of the
roadmap doc), plus the track's regression gate:

1. **"RS" spelled out.** Owner-reported: "RS" alone reads ambiguously as
   Rupees at a glance. Top Opportunities' relative-strength chip now reads
   "Rel Str" instead of "RS" — unambiguous, and `flex-wrap` was added to
   the symbol-metrics row as a safety net so the longer label can never
   overflow a narrow card.
2. **Quick Actions no longer triples the same announcement.** A completed
   full validation was announced three times: a toast, Recent Activity, and
   a persistent line under the Quick Actions buttons. The persistent line
   was the redundant one — removed for the `completed` state only; the
   `running` (live progress) and `failed` (error detail) states carry real
   information neither the toast nor Recent Activity shows, and are
   untouched.
3. **Evidence Attribution given real visual weight.** The single most
   decision-relevant sentence on the screen (why the regime/score is what
   it is, per ADR-005) read as a dense footer with less visual priority
   than the decorative summary tiles above it, and could silently truncate
   via `text-overflow: ellipsis`. Now has an accent left-border and
   accent-colored label (matching the app's existing icon/branding accent),
   and the text wraps instead of ever cutting off.
4. **Release gate.** New
   `tests/api/platform/test_market_intelligence_ux_release_gate.py` — 9
   tests locking in every MI-UX-1 through MI-UX-4 fix by inspecting the
   assembled static assets (same convention as
   `test_decision_chart_release_gate.py`): the corrected (not the flawed
   first-attempt) Top Opportunities capping approach, the shared "As of"
   phrase across all 4 sections, the failed-run alert treatment, the one
   metric-tile idiom, the Universe Eligible default, the grouped header,
   the spelled-out RS label, and the Quick Actions dedup.

Architectural note: presentation-only. No score, decision, regime, or
TradePlan value changed; no backend endpoint added or changed.

Validation note: full suite **1266 passed** (1257 + 9 new release-gate
tests). Live-verified against a read-only backup of the real database
through an isolated local instance on a never-before-used port (avoiding
the sub-resource caching artifact noted in MI-UX-3): confirmed "Rel Str —"
renders cleanly on-card with no overflow after expanding a capped card;
confirmed Quick Actions shows no stray text after a completed validation;
confirmed Evidence Attribution renders with the accent left-border and
highlighted label.

**No known P0–P2 finding from the original audit (§2 of the roadmap doc)
remains open.** This closes the Market Intelligence UX track pending owner
review of this final milestone.

---

### Fix pass: unbounded backup accumulation ate 28 GiB (owner-reported, 2026-08-03)

Owner: "my harddisk space is eaten by db/backups... i dont want any backup
more [than] 2 days," then, after seeing what's actually inside the database,
reframed to the real question — decisions/traces/journal/portfolio state
aren't re-fetchable market data, so is any backup worth keeping at all.

**Root cause:** `PortfolioService.reset_positions()` and
`DecisionsService.reset_decisions()` each write a best-effort auto-backup
before their CONFIRM-gated destructive action, but `create_backup()`
(`data/store/backup.py`, M1.6) never pruned anything — every reset, forever,
added a new ~304 MB full snapshot with zero cleanup. 137
`athena-pre-portfolio-reset-*.db` + 53 `athena-pre-decisions-reset-*.db`
files had accumulated (28 GiB total, `db/backups/`), plus 610 orphan
`.meta.json` sidecars with no matching `.db`. This — not this session's own
scratch files — was the real cause of the "no space left on device" failures
earlier in this session.

**Owner decision (asked explicitly, since it's a real product tradeoff, not
a pure engineering call):** given these auto-backups exist only as an undo
window for one specific reset action, not a retained history, the owner
chose to keep only the single most recent backup per reset type — not a
2-day window, not zero backups (zero would make CONFIRM on either reset a
true point of no return with no recovery path).

**Fix:** new `prune_backups(backup_dir, *, prefix, keep_newest)`
(`data/store/backup.py`) — deletes `{prefix}*.db` backups beyond the
`keep_newest` most recent (by mtime), each with its `.meta.json` sidecar;
scoped by `prefix` so pruning one reset type's backups never touches the
other's. Called from both `reset_positions()` and `reset_decisions()`
immediately after their own backup succeeds, with `keep_newest=1` — pruning
only after a successful new backup means a failed backup attempt never
leaves zero valid backups. Best-effort (a file that fails to delete is
skipped, not raised), matching the existing best-effort backup call it sits
next to. The owner-triggered manual "create backup" button (Live Operations
console, unrelated to either reset flow) was deliberately left untouched —
out of scope of what was asked.

Immediate cleanup: ran the same tested `prune_backups()` function directly
against the real `db/backups/` (not a separate ad-hoc script, so cleanup and
the new policy are guaranteed consistent) — removed all but the newest of
each reset type, plus stray `.tmp-journal` artifacts and the 610 orphan
`.meta.json` files. `db/backups/` went from 28 GiB to ~609 MiB; real disk
free space went from ~6.4 GiB to 33 GiB.

Architectural note: ops/data-lifecycle fix, not a domain or analytical
change. No score, decision, or TradePlan logic touched.

Tests: 5 new tests in `tests/data_layer/test_backup_restore.py`
(`TestPruneBackups` — keeps only newest N, never touches a different prefix,
`keep_newest=0` removes all matching, missing directory is a no-op, nothing
pruned when already under the keep count). Full suite: **1257 passed**.

---

---

### M-PERF-1: SQLite read-concurrency split (ADR-009) — approved

**Objective:** remove unnecessary SQLite read serialization while preserving
ATHENA's proven write correctness and the existing `SqliteRepository` API
contract — nothing more. Follows [ADR-009](adr/ADR-009-repository-read-concurrency.md)
(Accepted), itself written from evidence gathered across a live debugging
session that traced five distinct, individually-real bugs plus one
structural pattern: `SqliteRepository` serialized every read and write
through one shared connection + `RLock`, discarding the concurrency its own
`journal_mode=WAL` normally provides.

**Scope, exactly as ADR-009 specifies:** `_write`/`_write_many` unchanged;
`_query_one`/`_query_all` now route through the calling thread's
lazily-created, read-only (`mode=ro`) connection via `threading.local()`.
No public method signature changed. `:memory:` databases (config-preview and
canary's throwaway shadow repos) fall back to the shared connection/lock
unchanged — a second connection to `:memory:` would be a distinct, empty
database, discovered and fixed during implementation when it broke 7
existing tests.

**Tests:** `tests/data_layer/test_repository_concurrency.py` (12 new) covers
every ADR-009 acceptance item — reads don't wait on a slow write, concurrent
reads don't serialize, existing write serialization is unchanged, read-after-
write visibility (same-thread and cross-thread), read connections are
physically read-only, per-thread lifecycle/cleanup/isolation/recreation, the
`:memory:` fallback, and before/after timing reproductions of both the
ABLBL-validate-vs-`loadMarketIntelligence()` scenario and the Portfolio
Overview cold-load scenario traced live. Full suite: **1310 passed**, Ruff
clean (zero new violations beyond the 5 pre-existing, unrelated warnings
already in `repository.py` at HEAD).

See the Milestone Review Summary (delivered to the owner in-session) for
full before/after measurements, scope-compliance diff review, and write-path
regression verification.

A second, independent bottleneck (`SqlitePipelineRunProvider.get_runs()`'s
N+1 detail-fetch, ~8.8s standalone, unrelated to locking) was found
underneath this fix once it removed the contention masking it, and fixed
separately — see `IMPLEMENTATION_SUMMARY.md`'s "pipelines/runs N+1
detail-fetch" entry, not part of ADR-009's own scope.

Status: ✅ Approved — owner live-tested multiple symbols post-restart,
confirmed under 10s end to end.

---

---

## DarvaX satellite track (parallel workstream — ADR-010)

DarvaX is an **isolated, opt-in satellite module**, not part of ATHENA's core
roadmap. Per ADR-010 (Accepted 2026-08-10) it is a *parallel advisory lane* and
never contributes to ATHENA's scoring, confidence, risk, Decision, TradePlan,
universe, or decision pipeline. **DX milestones are never mixed with ATHENA
Phase 9+ milestones or bundled into the same change set.**

| Milestone | Scope | Status |
|---|---|---|
| **DX-1** Isolation foundation | Module skeleton, DarvaX-owned config (ships `enabled: false`), own `db/darvax.db` + independent schema versioning, `DarvaxMarketDataPort`, guarded mount seam with explicit enabled-but-absent failure, full 12-point isolation suite. **Zero trading logic.** | ✅ Approved (2026-08-11) |
| **DX-2** Methodology primitives | Exactly seven pure functions — Darvas box, ZigZag swings, distance-to-ATH, range contraction, volume expansion, inside bar, Fibonacci levels + zone. Decimal throughout, no clock/config/IO, hand-worked fixtures. **Measurements only, zero signals.** | ✅ Approved (2026-08-11) |
| **DX-3** Signal engine | Six-state box breakout/retest machine referencing the *topmost* box per Darvas rules A/B/C/D; three stop policies (canonical 10%, tight 1%, EMA ladder) with DarvaX's own EMA; `DarvaxSignal` persisted to `darvax.db` (schema v2) with computed explanation + evidence trace + methodology digest. **Never an ATHENA Decision.** | ✅ Approved (2026-08-11) |
| **DX-4** `/darvax/` surface | DarvaX's own page + assets and its own authenticated API (`/signals`, `/signals/{id}`, `/scan`), plus a bounded scan service. Auth **delegated** to ATHENA (no second credential store). Experimental label on every payload and in the page banner. Touches no ATHENA dashboard asset. | ✅ Approved (2026-08-11) |
| **DX-4b** Dashboard tab | Per ADR-010 **Amendment 1** (Accepted 2026-08-11): DarvaX appears as a sidebar tab alongside ATHENA's own. A DarvaX-served `tab.js` injects one nav item + one panel at runtime and embeds `/darvax/?embedded=1` in a lazy same-origin iframe. ATHENA's only change is one deferred `<script>` tag in `index.html`, which **is** the flag guard — disabled/deleted DarvaX ⇒ 404 ⇒ nothing injected. Self-manages activation because ATHENA's nav/pane NodeLists are static. | ✅ Approved (2026-08-14) |
| **DX-4a** Performance evidence | Measure ATHENA responsiveness with DarvaX disabled vs enabled; quantify host-level contention. Harness `tests/darvax/bench/darvax_perf_bench.py` (A disabled / B enabled-idle / C enabled-and-scanning, plus a `--live` workstation probe); evidence in `docs/design/DARVAX-PERFORMANCE-EVIDENCE.md`. **Result:** mounting costs nothing measurable; realistic cadence shows no contention (≤1.01×); worst-case hot loop 2.5–5.3× on cheap routes but ≤14 ms absolute. **No mitigation recommended.** | ✅ Approved (2026-08-14) |
| **DX-5** Validation evidence | DarvaX-owned harness (`darvax/validation/`) replaying the DX-3 engine bar-by-bar with structural no-lookahead; expectancy, win/loss, drawdown, sample size, and a **sufficiency gate** that keeps the label on unless ≥200 closed trades *and* ≥500 trading days. **Result: `EXPERIMENTAL_UNVALIDATED` stands** — the ledger holds only 82 trading days (`ingestion.lookback_days: 90`), and on that sample both stop policies are negative. Measured the deck's 1%-vs-10% contradiction: the 1% stop is noise-level (96% of exits are stops, 4.3% win rate). Evidence: `docs/design/DARVAX-VALIDATION-EVIDENCE.md`. 19 tests | ✅ Approved (2026-08-16) |
| **DX-6a** Screening engine | Eligibility taxonomy (ACTIONABLE/WATCH/EXIT_RELEVANT/NOT_ELIGIBLE, pure functions of `signal_type` → DAR-CARD rules), **two** measured ranking quantities (distance-to-trigger, box height — bars-in-box and volume expansion deferred, see below), `darvax_sweeps` + `darvax_screen_results` + schema v3, 32 tests. **No sweep job, no UI, no API.** Design: `docs/design/DARVAX-SCREENER-DESIGN.md` | ✅ Approved (2026-08-14) |
| **DX-6b** Universe sweep + API | Single-flight owner-triggered background sweep (409 on concurrent start, cancellable, partial results preserved, per-instrument failure isolation), batched beneath `scan.max_instruments`; five `/screen` endpoints plus a `signal_type` filter on `GET /api/signals`; retention pruning. Owner decisions (2026-08-14): **all 528 ledger instruments**, **daily only**, **keep 30 sweeps**. Schema v3→v4 after a live sweep exposed the WATCH tier ordering alphabetically. 30 tests | ✅ Approved (2026-08-15) |
| **DX-6c** Screener UX | Tier groups with counts and collapse, the box-range visualisation (floor/ceiling/close/trigger, plain CSS, no library), per-column client-side sort and symbol filter, row expansion fetching persisted evidence on demand, and every honest state — no-sweep, running with progress, cancel, skipped-with-reasons, stale as-of, methodology-digest mismatch. Screener and the DX-4 ad-hoc scan share the page behind a view switch. 23 tests | ✅ Approved (2026-08-15) |
| **DX-6d** Universe-scale perf re-measure | Harness gained `--load sweep`, driving the real `SweepRunner` over all 528 instruments. **Result:** universe scale did *not* worsen contention — the worst case is thread-bound, not instrument-bound, and matches DX-4a's within noise; realistic cadence shows none at all (≤1.01×); a warm sweep takes 0.23s; storage bounded at 12.6 MB by `retain_sweeps: 30`. **No mitigation warranted.** Evidence: `docs/design/DARVAX-PERFORMANCE-EVIDENCE.md` §7a | ✅ Approved (2026-08-15) |

**Source-quality caveat on record:** the DarvaX deck ships no backtest evidence
of any kind — only cherry-picked winners and testimonial screenshots — and its
author disclaims it in the deck itself.

**DX-5 outcome (2026-08-15):** the label **stays**. DarvaX built its own
validation harness and ran it; the ledger's 82 trading days cannot clear the
500-day sufficiency floor, and on the sample that does exist both stop policies
are negative. The blocker is `ingestion.lookback_days: 90` — a configuration
limit, not a Kite limit — so a deeper backfill is the one change that would let
DX-5 produce real evidence. See `docs/design/DARVAX-VALIDATION-EVIDENCE.md`.

### DarvaX advisor track (DX-7, design: `docs/design/DARVAX-ADVISOR-UX-DESIGN.md`)

Owner decisions recorded in the design §4: **1a** DarvaX keeps its own position
list (not the recommendation — accepted with the drift risk stated), **2a** the
shortlist ranks by nearest-to-trigger rather than a "best" score DarvaX cannot
support, **3b** the unvalidated warning rides on each risk-bearing action chip.

| Milestone | Scope | Status |
|---|---|---|
| **DX-7a** Actions as data | `DarvaxAction` + `action_reason` computed by the engine and persisted (schema v4→v5); `RISK_BEARING_ACTIONS` and a `risk_bearing` API flag so the badge set cannot drift in JS. Fixed `rank_tier`'s field-by-field rebuild, which had been silently dropping newly added fields. 30 tests | 🔄 Ready for review |
| **DX-7b** Positions | `darvax_positions` (schema v5→v6) with a partial unique index for one open position per instrument; `HOLD` and position-confirmed `EXIT` derived from the DAR-CARD applied literally; stop frozen at entry with its basis. Positions are passed *into* the screening engine, which still performs no lookups. Also fixed a test-isolation defect that let DarvaX API tests write real sweeps into the owner's `db/darvax.db`. 39 tests | 🔄 Ready for review |
| **DX-7c** Advisor dashboard | Three zones: positions with per-holding advice, a 10-card shortlist in the engine's own rank order, and the DX-6c tier table kept as zone 3. Unvalidated badge on every entry chip, carrying the DX-5 attribution finding. 33 tests | 🔄 Ready for review |

### DarvaX levels track (DX-9, design: `docs/design/DARVAX-DETAIL-TABLE-DESIGN.md`)

Owner asked for the simple view's trade values in the detailed view too, and for
a new view type carrying proper trading levels. He delegated the four open design
decisions; answers are recorded in the design §5.

**The finding that shaped it:** a trigger and stop exist for only **117 of 2,191
rows (5%)** — DX-3 records them only where a breakout produced an entry. Literal
parity would give three columns that are 95% empty, so "Buy above" instead shows
the level the engine already ranks against (`trigger_price`, else `box_top`,
marked), and a blank stop is treated as information: *not a trade yet*.

**Second finding:** the level *ordering* varies, and the variation is a real
trading fact the UI has never shown. XTRANET's stop (₹141.30) sits **above** its
breakout ceiling (₹136.90); BI's stop (₹60.29) sits **below** its ceiling (₹75).
Same 10% rule, materially different trades — one exits above the breakout, the
other gives the whole breakout back.

| Milestone | Scope | Status |
|---|---|---|
| **DX-9a** | Detailed table carries the trade values at last: **twelve columns under a banded three-group super-header** (identity / THE TRADE / context) — action chip, `Now`, `Buy above`, `Stop`, `Risk now`, `To buy level`, plus liquidity in the context block. `State` folded under the symbol rather than dropped (the persisted explanation is phrased in its terms); sticky symbol column. Risk and liquidity arithmetic **shared with the Levels card** so the two views cannot disagree. 11 tests | 🔄 Ready for review |
| **DX-9b** | Verified live against a 2,191-row sweep generated with current code: 12 headers, super-header spans summing to exactly 12, 627 rows all with matching cell counts, sticky symbol column, absent levels rendering `—` rather than `₹0`, and action chips confirmed **actually styled** via computed colour rather than by their class name | 🔄 Ready for review |
| **DX-9c** | Persist the stop-versus-ceiling comparison engine-side, schema v7→v8 (ADR-005). Measured on a live sweep: **50 stops above the breakout level, 65 below** — the majority of entries would give the whole breakout back if stopped. Every one of the 115 entries carries the comparison; no non-entry does. 31 tests (with DX-9d) | 🔄 Ready for review |
| **DX-9d** | New **Levels** view: three-way mode switch, a to-scale price ladder per instrument in plain CSS — box as a filled band, breakout zone hatched, entry/stop/now marked, plus **your own entry and stop** styled apart from the method's. Restricted to rows with levels (1,557 `NO_ENTRY` excluded) | 🔄 Ready for review |

Three views, three questions, no redundancy: **Advisor** — what do I do today?
**Levels** — where are the prices? **Table** — show me everything.

**Verified by measuring 128 rendered ladders**, not by eye. Three defects the
browser found and no fixture would have:

1. **A held position's own stop was not on its ladder** — it appeared as a line
   of text under the chart, which is backwards for the one card where the level
   protecting money matters most. Now drawn, and styled apart from the method's
   stop: yours was frozen when the position was recorded, the method's is
   recomputed every screen, and blurring them would let a prospective level read
   as a live one.
2. **Labels collided** where two levels sit close together — `Now ₹11,650` and
   `Floor ₹11,607` are 0.4% apart, about 2% of the ladder. The label is nudged
   and **the line is not**: moving the line would make the chart lie.
3. **A first fix left 16 of 488 label pairs still overlapping**, because the
   minimum gap (14px) was under the measured label height (14.7–15.5px); and a
   purely forward pass then pushed 5 labels out of the card entirely. Fixed with
   a backward clamp. Final: **0 overlaps, 0 escapes, worst gap +2.5px.**

Explicitly excluded, and recorded so it is not revisited by accident: no
candlestick chart (price history is not what the method reads, and ADR-004 rules
out a charting library), no target line (the method has none), and no colour that
implies quality — colour marks the *kind* of level, never how good a candidate is.

---

### DarvaX filters & targets track (DX-10, design: `docs/design/DARVAX-FILTERS-AND-TARGETS-DESIGN.md`)

Owner asked for market-cap and volume filters and for a target price, then
delegated the choices: *"you can decide whichever is best for trading and more
conviction and profitable."* What was buildable honestly, and what was not:

| Milestone | Scope | Status |
|---|---|---|
| **DX-10a** | **Liquidity, not market cap.** ATHENA holds no capitalisation data anywhere, and inventing a proxy would be inventing a fundamental. Median traded value over 20 sessions, persisted engine-side (schema v8→v9); **median not mean, so a single 500× volume spike moves it not at all** (verified). Measured at sweep time — the screening engine has no market-data access by design, so the sweep computes it and hands it down | 🔄 Ready for review |
| **DX-10b** | Three conviction filters: where the stop sits relative to the breakout, liquidity threshold, box tightness. Measured funnel on a real sweep: 117 → **50** (stop above breakout) → **23** (≥₹25 cr/day) → **10** (box ≤10%) | 🔄 Ready for review |
| **DX-10c** | **R-multiples instead of a target.** The method has no profit target — Darvas trailed the stop-loss, and the DAR-CARD's only exits are the 10% stop-loss (B) and the box floor (C), which *is* the trail. So the card shows `R = buy level − stop-loss` with 1R/2R/3R and an `already +N.R` marker, labelled as a scale and not a forecast. Plus: the liquidity filter **disables itself with a stated reason** on a sweep that recorded none, and the page no longer quotes a sweep-record count smaller than the rows it is displaying | 🔄 Ready for review |
| **DX-12a** | **50/100-session EMA trend context**, requested directly by the owner ("adding 50 and 100 ema to darvax screener/advisor"). **Not a DAR-CARD rule** — Darvas' method is pure price action; the deck's only EMA usage is the 5/10/20/200 stop ladder, an exit rule, not a trend filter. Computed in `sweep.py` (one combined candle read now serves both liquidity and trend), threaded into `screen_signal` exactly like liquidity, persisted on two new nullable `ScreenResult` columns (schema v9→v10). Surfaced in the Table view as two new columns under "context", plus a 4th filter ("Trend: any" / above / below both EMAs) following the same fact-in-the-option, meaning-in-the-note split as the stop-loss and box-height filters. Guide (§5, §7) updated with grounded cross-checks against `trend.py`'s own constants. 29 new tests. Measured on a real sweep: EMA(50) computable for 2,149 of 2,191 instruments, EMA(100) for 2,041 — fewer, since it needs more history. **Scope note:** the owner asked for Advisor-badge and Levels-view treatment too; split into DX-12b, now the next design gate, per the "split before implementing" rule — three UI surfaces plus a schema change was too large for one sitting | ✅ Approved |
| **DX-11** | **In-app methodology guide.** Owner asked for a "world class ux reading guide... complete information... each and every minute detail." A header-triggered dialog with a sticky TOC across 12 sections: what DarvaX is, the Darvas box (with an SVG diagram), the four DAR-CARD rules quoted verbatim, all seven actions, every card field, the three views, the three filters, the stop-loss self-contradiction (10% canonical vs 1% tight), liquidity, the screened universe, the DX-5 validation gate, and what DarvaX will not do. Every quote and threshold is cross-checked in `test_dx11_guide.py` against the exact source it describes (`DAR_CARD_TEXT`, `config.py`, `validation/summary.py`, `screening/liquidity.py`), so the guide cannot silently drift from the methodology. 20 tests | 🔄 Ready for review |
| **DX-10cʹ** | **Plain language pass**, after the owner reported the DX-10b filter names as *"more confusing and not at all user friendly"* and asked *"stop means stop loss?"*. Every label DarvaX writes now says **stop-loss** in full (filter, table column, ladder row, `Your stop-loss`, entry field); engine-persisted prose keeps its own wording per ADR-005. Filter options carry the **fact**, the note below carries the **meaning** — an option is a label, and the intermediate attempt that made it a sentence read worse than the jargon it replaced. Box height states explicitly that it is *not* measured from the buy level, because on a real sweep the buy level sits above the ceiling on 107 of 117 rows but **inside the box on 10**. 18 tests | 🔄 Ready for review |
| **DX-10d** | Volume-expansion filter (breakout volume vs its own median). Requires extending the **DX-3 signal engine** to measure and persist it, and **cannot be backfilled** onto existing signals. Not started — needs owner approval as its own milestone | ⏳ Planned |
| **DX-10e** | Acquire and version a market-cap source, if wanted. No provider currently supplies it | ⏸ Deferred |

**Three defects found only by running it**, each invisible to the whole suite:

1. **The page did not boot at all.** DX-10b's filter selectors were never added
   to the element map — the patch anchored on a line with a trailing comma that
   the last entry in an object literal does not have — so `S.fStop.addEventListener`
   threw at initialisation and aborted the script. Static HTML rendered, nothing
   else did. 1,924 tests passed because they asserted that strings appeared in
   the source, not that references resolved.
2. **Every price on the Levels card read `₹₹6.7`.** A second `function money()`
   was declared while one already existed further down the file; the later
   declaration wins, so callers of the new signature silently got the old helper
   — which adds the symbol itself, and drops a trailing zero. Now one
   `rupees()`, and a test that fails on **any** duplicated function name.
3. **A sweep read as unstarted while displaying 2,191 rows.** Observed directly
   on a copy of the owner's live database at ~18:55 IST: sweep
   `swp-20260818-110247` had all 2,191 result rows persisted while its record
   still said `state="running", evaluated=0`. A fresh process reading that record
   printed *"0 instrument(s) screened"* above a table of 2,191 rows, while the
   process that had run the sweep held the real figure in memory and showed
   2,191.

   **Scope corrected on re-measurement.** By 19:17 IST that same record read
   `completed, evaluated=2191`, so the contradiction was a **transient window**,
   not permanent loss — the runner saves results before the completion record,
   and a reader landing between the two writes sees the inconsistent state.
   Whether the record is ever permanently lost (a process killed in that window)
   was **not determined** and is not claimed. The UI fix stands either way,
   because the window is real and a fresh process can land in it.

**Open, needs owner decision — sweep write atomicity.** Lower severity than
first written (the observed case self-corrected), but the two-write window is
real. The fix is not obvious enough to make unilaterally: saving the record
before the results would claim coverage that a crash then invalidates, which is
worse. Options are one transaction spanning both writes, or deriving display
state from the presence of results. Either touches `screening/sweep.py`
persistence ordering and belongs in its own milestone.

**Closed without needing the owner — the repeated stop-loss warning.** Asked
twice during DX-9/DX-10: 65 of 115 entries carry the stop-loss-below-breakout
sentence, so should it be summarised once at the top instead of appearing on
every card? **No.** The sentence is not boilerplate — it is engine-computed
per-card data carrying that instrument's own figures (*"₹58.28 below the
breakout level of ₹698"* against *"₹22.01 below … ₹174.97"*). Hoisting it into
one summary line would replace 65 specific measurements with a count, which is
a loss of information dressed as a reduction in clutter. It stays per card.

**Also unfixed, recorded so it is not lost** (`SYMBOL-UNIVERSE-INVESTIGATION.md`
§13): group membership is never retracted on re-run, and 270 iNAV rows resolve
into `darvax_discovery`.

---

### DarvaX plain-UI track (DX-8, design: `docs/design/DARVAX-PLAIN-UI-DESIGN.md`)

Owner's verdict on DX-7c: *not user friendly, very complicated, not able to
understand for a normal user.* Decisions in the design §5: **1b** a second
plain-language field beside the technical one, **2a** simple by default with the
table one click away, **3a** risk per share only (no position sizing — that is
ATHENA's `sizing/` and ADR-010 keeps DarvaX out of it).

| Milestone | Scope | Status |
|---|---|---|
| **DX-8a** | `stop_price`/`stop_basis` copied onto `ScreenResult` and `action_reason_plain` persisted beside the technical reason (schema v6→v7). **The stop was a correctness gap, not presentation**: rule B mandates it, `DarvaxSignal` always carried it, and the screener could not show it — so a screen recommended entries without the exit that makes them survivable. Guarded against the two registers drifting: the plain one may cite no rule, the technical one must, and they must differ. 15 tests | 🔄 Ready for review |
| **DX-8b** | The plain screen: sell → hold → buy in urgency order, trade tickets carrying buy-above / stop / risk-per-share / now, plain vocabulary (`ACTIONABLE`→Buy, `BREAKOUT_RETEST`→Buy on dip, and *"through"*→*"already above the buy level"*, which meant good news and read like an error), long tail collapsed to one line, DX-6c table behind a toggle. 19 tests | 🔄 Ready for review |
| **DX-8c** | Every honest state re-verified at the new layout, live. **Two were hidden by the restructure**: the skip report ended up inside "Detailed view" and the no-sweep message inside the advisor view — each rendering perfectly in one mode and invisible in the other. Both moved out; ancestry now asserted with a real HTML parser after a regex version reported success while being wrong. 16 tests | 🔄 Ready for review |

**States verified in the browser**, not by fixture: no sweep (both views) · sweep
running, sampled mid-flight through `enumerating → Evaluating universe`, 0 → 950
→ 1550 → 2150, bar 0 → 98.1% · cancelled at 1,450 of 2,191 with results kept and
flagged `partial` · methodology-digest mismatch, flagged alongside `partial` and
present in both views · staleness, which correctly *disappeared* once the daily
cycle advanced the ledger to 2026-08-17.

Two defects found only by looking: DX-8b's restructure deleted the position
form and row handlers along with the markup they were bound to — everything
rendered and nothing worked — and risk per share printed `₹6.7` because a
two-decimal value was passed through a helper that re-parses to a Number. Both
are covered now, including a test that fails if any `getElementById` points at
markup the page no longer defines.

---

**Verified in a real browser** against the live 2,191-instrument universe, which
caught three things the tests did not: `.posform { display:flex }` defeating the
`hidden` attribute so the entry form rendered permanently open; a `limit=2000`
row cap silently truncating a 2,191-row sweep; and the meta line reporting the
truncated count as the number screened. All three are fixed and covered.

---

**DX-5 re-run (2026-08-16) — supersedes the reading above.** After SU-1→SU-6,
the `le=365` bound was measured rather than assumed (Kite returns a full span up
to **3,650 days in one request**), raised to `le=3650`, and a one-off backfill
took the ledger from 82 to **744 trading days** in 3.5 minutes. Re-run results:

- **Both policies reversed sign.** Canonical 10%: expectancy **+4.09%** (was
  −3.62%), 37.9% win rate, 1,975 closed trades. The earlier negative reading was
  a small-sample artifact — as this document's own caveat predicted — and is
  retracted.
- **The gate now passes on sufficiency, and that is not enough.** Stress-testing
  outside the harness separates the two policies the gate labels identically:
  canonical survives a 1% round-trip cost (+3.09%) *and* deleting its best 1% of
  trades (+2.40%); the tight 1% policy draws **70.8% of its P&L from its top 1%
  of trades** and collapses to +0.38% without them. **ADR-010's "1% is removed by
  ordinary noise" is confirmed, by a result that superficially looks positive.**
  The deck's 10%-vs-1% contradiction is settled in favour of canonical.
- **Negative controls attribute most of the headline elsewhere.** Random entries
  with *identical* exits return **+2.80%**; return-shuffled series return
  **+2.41%**. Roughly two-thirds of the +4.09% is the exit rule operating in a
  rising market, not Darvas box detection. The detection increment is **+1.23pp**
  and only marginally significant (t = 2.03; 0/12 random seeds beat it, p ≈ 0.08)
  — suggestive, not established. **"DarvaX has a +4.09% expectancy" is a
  misleading summary.** The screener itself is selective and structurally sound:
  1.7% actionable across 530 instruments, zero breakouts on synthetic
  monotonic/flat series.
- **The label still stands.** Survivorship bias over three years is unquantified
  and biases upward; the reported `max_drawdown` was traced to a
  full-capital-compounding artifact and should not be quoted; there is no
  out-of-sample split. Removing `EXPERIMENTAL_UNVALIDATED` is an owner decision
  and was not taken. Five follow-ups are proposed in
  `docs/design/DARVAX-VALIDATION-EVIDENCE.md` §7, none implemented.

---

## Symbol master & scanner universes track (ADR-011 — **Accepted** 2026-08-15)

ADR-011 Accepted 2026-08-15. Investigation and impact analysis:
`docs/design/SYMBOL-UNIVERSE-INVESTIGATION.md`.

Root cause on record: the scanner universe *is* the ingested candle universe,
and ingestion is scoped by the owner-curated `owner_candidates` table (518 rows
at the time of investigation). `RATNAVEER` and `PNGSREVA` were absent from that
list — not excluded by any index, series or SME rule. A prior hypothesis that
the universe was Nifty-500-shaped was **disproven**: `JGCHEM` is in no index
file and was ingested normally.

| Milestone | Scope | Status |
|---|---|---|
| **SU-1** Symbol master | `athena/symbols/` (models, pure suffix classification, catalogue builder) + `symbol_master` table at schema v13, with `series_source` and `classification_reason` provenance. Re-derives series rather than trusting the provider's fabricated `"EQ"`. Verified on the live catalogue: **10,197 records in 0.1s**, board split MAINBOARD 3,390 / UNKNOWN 6,368 / SME 439. **No consumer changes** — `instruments` untouched. `instrument_token` deliberately dropped (ADR-002). 26 tests | ✅ Approved (2026-08-15) |
| **SU-2** Group membership | `athena/symbols/groups.py` + `symbol_group` at schema v14: **dated** many-to-many membership, no duplicated symbol rows. Loads 12 index groups from the existing checksum-verified snapshot, `NSE_MAINBOARD`/`NSE_SME` from the symbol master, and `OWNER_CANDIDATES` from the live table. `NSE_ALL_ELIGIBLE_EQUITY` deliberately **not** materialised (rule-defined, SU-4). Live: 15 groups, 351 index memberships, 0 unresolved constituents. **Found a live defect** — see `SYMBOL-UNIVERSE-INVESTIGATION.md` §10. 21 tests | ✅ Approved (2026-08-15) |
| **SU-3** Universe resolver | `config/universes.json` + `athena/symbols/universes.py`. **`athena_core` → `OWNER_CANDIDATES`, eligibility `none`, asserted set-identical to the live table** (ADR-011 §3.1). Groups unioned and sorted; `as_of` resolves historical membership; empty groups reported rather than swallowed. An **unimplemented eligibility profile raises** rather than returning an unfiltered set under a filtered universe's name. Live: 5 of 6 universes resolve — athena_core 518, mainboard_equity 3,390, broad_scanner 200, midcap 100, largecap 50; `darvax_discovery` correctly refuses until SU-4. 34 tests | ✅ Approved (2026-08-15) |
| **SU-4** Eligibility profiles | `athena/symbols/eligibility.py`: named, ordered rule sets where **every exclusion is attributable to one rule with a reason in words**. `darvax_discovery` = known board + ordinary equity series (excludes BE/BZ/IV trade-for-trade and surveillance) + not-a-fund. **No thresholds invented** — liquidity is unmeasurable from the catalogue (`last_price` is 0 for all rows) and only measurable from candles that exist for already-ingested symbols, which is circular for discovery. SME handled as group composition, not a filter. Live: `darvax_discovery` resolves **2,728** of 3,390 mainboard symbols, excluding 289 restricted-series + 373 funds; all three owner reference symbols included. 20 tests | ✅ Approved (2026-08-15) |
| **SU-5** Coverage planner | `athena/symbols/coverage.py` + `candle_coverage()`: **planning fetches nothing** (2,728 symbols planned in 0.04s via one chunked query) and **execution is bounded by a required limit with no default**, with per-symbol failure isolation. Coverage declared per universe in config with provenance — DarvaX's 400 bars is its own `scan.lookback_bars`, not a number chosen here. **Live finding: 0 of 2,728 discovery symbols and 0 of 518 `athena_core` symbols meet 400 bars**, because the ledger holds ~82; a full backfill is ~2,728 requests / ~15 min, and 400 bars is unreachable in one pass under the `lookback_days ≤ 365` cap. 18 tests | ✅ Approved (2026-08-15) |
| **SU-6** DarvaX opt-in + re-measure | `resolved_universe` table at schema v15; DarvaX's own adapter gains `with_universe()` and its config an opt-in `universe` key (**default `None` = today's behaviour**). A universe reaches DarvaX as **data through its existing port** — a test asserts DarvaX imports no ATHENA universe machinery and the mount seam never mentions a universe, so ADR-010's pinned surface is unchanged. Re-measured at 528: 2.25–3.97×, consistent with DX-6d. 12 tests. **Opted in 2026-08-16** after the classification fix and a 2,115-symbol backfill: DarvaX now discovers over **2,191 instruments (4.1×)**, and all three owner-supplied symbols — RATNAVEER, PNGSREVA, JGCHEM — screen **ACTIONABLE / BREAKOUT (rule B)**, closing the investigation that started the track. Re-measured at 2,191: contention unchanged (1.48–5.00× worst case vs 1.50–5.08× at 528); realistic cadence ≤1.08×; sweep 3.51s over 2,191 with 0 skipped. Evidence: `docs/design/DARVAX-PERFORMANCE-EVIDENCE.md` §7b | 🔄 Ready for review |

**Latent defect to fix regardless of the ADR:** `config/providers/kite.json` sets
`symbols: ["INFY"]`, inert only because every real ingest path overrides it. An
ingest without a candidate scope would silently collapse the universe to INFY
plus index instruments.

---

*Status legend: a milestone is "In Progress" (🔄) when actively being designed or built, "Approved" (✅) only when the owner signs off. Never two milestones in flight.*
