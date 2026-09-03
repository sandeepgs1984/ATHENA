# EM-7 Discovery — Explosive Move Radar Live Shadow Validation

**Status:** EM-7 DISCOVERY COMPLETE — implementation NOT started, NOT
authorized by this document. Owner/Chief Architect authorized
discovery-only on 2026-09-03, following EM-0 through EM-6B.1 all
owner-approved/closed.

Everything below is source-grounded (file:line citations throughout),
produced by direct repository inspection — not inferred from EM-7's
number or from prior conversation memory.

---

## 1. Executive summary

EM-7 has **no owner-ratified implementation contract anywhere** in this
repository. Two documents give it real scope content — ADR-012 §10 and
`docs/design/ATHENA-EXPLOSIVE-MOVE-RADAR-ROADMAP.md` — and they agree
with each other word-for-word on the substance: EM-7 is **live shadow
validation**. Run the already-frozen, already-calibrated EM-4E/EM-5
pipeline against genuinely arriving real-time data, without it affecting
canonical ATHENA in any way, and measure two distinct things: (a)
statistical/predictive health (precision, lift, calibration, MFE, MAE,
misses, false positives, regime drift, data failures, latency) and (b)
canonical-system performance impact (EMR-disabled vs. EMR-shadow-mode
comparison across dashboard load time, symbol-validation latency,
canonical cycle timing, DB query latency/volume, CPU/memory, EMR
scanner-cycle duration). Neither document specifies *how* — no scheduler
mechanism, no checkpoint cadence for live operation, no universe scope,
no scanner-hardening requirement is decided anywhere.

The single most important finding of this discovery: **nothing currently
invokes EM-5's live scanner (`run_scan_cycle`) outside of tests and an
offline canary.** There is no CLI command, no cron entry, no scheduler
wiring, no config-driven enable gate — nothing. `db/emr.db` does not
exist in production for exactly this reason. EM-7 cannot merely "start
measuring" — it first needs an actual live-invocation mechanism, which
does not exist today in any form.

A second, real finding: the scanner itself (`run_scan_cycle`) has three
genuine correctness gaps that make it unsafe to run unattended today —
zero exception handling (a mid-scan crash leaves an orphaned `RUNNING`
row forever; no `FAILED`/`PARTIAL` state exists anywhere in the domain
model), non-idempotent candidate/transition persistence (replaying the
same deterministic `run_id` duplicates every row, since `emr_candidates`/
`emr_transitions` have no uniqueness constraint), and no concurrency
lock. These are not new EM-7 requirements to invent — they are
pre-existing, real gaps a discovery of "can this run unattended" is
obligated to surface honestly.

The good news: the hard architectural problem — how to get live market
data into EMR without duplicating ATHENA's own provider traffic — is
**already solved**. `EmrMarketDataPort`/`SqliteEmrMarketDataAdapter`
(EM-5) already read exclusively from already-ingested `db/athena.db`
candles via a narrow, read-only Protocol, deliberately mirroring
DarvaX's own ADR-010 read-port pattern. The only live network call
anywhere in the EMR pipeline is one authorized, narrow, batched Kite
`/quote` seam for the checkpoint reference price.

Recommended direction (not authorized): a new, **isolated EMR scheduled
worker** — its own invocation mechanism, own lock, own `db/emr.db`,
config-gated enable/disable (mirroring DarvaX's `config.enabled`
pattern) — sequenced behind first fixing the three scanner-correctness
gaps. This requires a new ADR (or an ADR-012 amendment); recommendation
only, not drafted here.

## 2. Scope / non-scope

**In scope:** reconstructing the authoritative EMR milestone chain;
extracting EM-7's actual (thin) documented scope; auditing the existing
EMR pipeline end-to-end from source; identifying the real gap between
"EM-6 closed" and "EM-7 can begin"; architecture options; a recommended
sub-milestone sequence; a small set of owner policy questions.

**Explicitly out of scope, not done here:** any EM-7 implementation; any
new production worker/scheduler code; any change to `run_scan_cycle`,
`EmrRepository`, or any other `explosive_move/` source; creating or
initializing `db/emr.db`; triggering an EMR scan; adding EMR scheduling
of any kind; drafting an ADR (recommendation only); starting EM-8; any
change to the ID track (ID-7P0 remains in its own passive wait state,
untouched); any change to DarvaX.

## 3. Authoritative EMR milestone state

Source: `docs/MILESTONES.md` (EMR table), corroborated by
`docs/ATHENA-EMR-HANDOFF.md`. `docs/MILESTONES.md` and
`IMPLEMENTATION_SUMMARY.md` are the current, authoritative sources —
**`ATHENA_BRIEFING.md`'s EMR repo-map row was found stale** (still says
"no UI... production recommendation" even though EM-6, the UI milestone,
closed the same day) — flagged for correction in §31.

| Milestone | Status |
|---|---|
| EM-0 | ✅ Owner approved / closed 2026-08-21 (isolated EMR architecture boundary) |
| EM-1a | ✅ Approved 2026-08-21, superseded by EM-1r5's re-audit |
| EM-1r1–EM-1r5 | ✅ All approved 2026-08-21 through 2026-08-26 |
| EM-1b | ✅ Approved 2026-08-27 (label dataset + chronological partitions) |
| EM-1c (+ prereq) | ✅ Approved 2026-08-27 (base rates, min-support policy n≥1,000/k≥10) |
| EM-2 | ✅ Approved 2026-08-27 (28-field evidence contract, 206,351 symbol-day rows) |
| EM-3 v1 | ✅ Approved 2026-08-27 (185,004 cells) |
| EM-4A/B/C/D/E | ✅ All approved 2026-08-27/28 — see §5 for exact frozen contract |
| EM-5 (+ Track B/B.1) | ✅ Owner approved / closed 2026-09-01 — see §6 |
| EM-6/EM-6A/EM-6B/EM-6B.1 | ✅ All owner approved / closed 2026-09-03 — see §7 |
| **EM-7** | **NOT STARTED / Planned** — `docs/MILESTONES.md`: "Run isolated shadow validation and OFF-vs-shadow performance comparison" |
| **EM-8** | **NOT STARTED / Planned** — "Decide research-only, continued shadow, retirement, or a new integration ADR" |

No EMR milestone itself is classified "DEFERRED" — that word appears only
against two individual *risk items* inside EM-6's own discovery risk
register (regime concentration, symbol concentration), explicitly flagged
as "worth EM-7 attention," not a milestone status.

## 4. ADR-012 frozen isolation contract

`docs/adr/ADR-012-explosive-move-radar-boundary.md`. Core mandate:
self-contained `athena.explosive_move` module, own SQLite DB/schema, no
provider clients beyond one narrow authorized seam, explicit prohibition
on modifying canonical `ScoringEngine`/`Confidence`/`Risk`/`Decision`/
`TradePlan`/EMR/DarvaX, and — directly relevant to EM-7 — §10
"Performance isolation": *"EM-5 must measure and persist scanner
duration and database query volume. EM-7 must compare EMR disabled with
EMR shadow mode for dashboard load time, symbol-validation latency,
canonical cycle timing, database query latency and volume, CPU and
memory use, and EMR scanner-cycle duration. A material regression
blocks promotion until it is explained, bounded, and owner-approved."*
Required controls: *"EM-8 requires owner approval and a separate ADR for
canonical integration."* This ADR remains frozen and unmodified by this
discovery.

## 5. EM-4 frozen modeling contract

- **EM-4A** — deterministic evidence score: a plain predeclared vote
  (`src/athena/explosive_move/deterministic_score.py`), never a fitted
  model; `score = (positive_votes − negative_votes) / total_votes`,
  `UNKNOWN` when no votes.
- **EM-4B** — 18 pooled logistic baselines (3 families × 6 thresholds),
  strictly chronological session-grouped expanding-window CV, PR-AUC
  selection metric only. Real run: 518 instruments, 1,857,159 joined
  rows. `C=0.01` selected for 13/18 models.
- **EM-4C** — real VALIDATION comparison: logistic beats deterministic on
  PR-AUC in **18/18** combinations (e.g. TOUCH_10: 0.178 vs 0.034).
  TOUCH_10 real excursion: MFE mean 13.4%, MAE mean 2.6%, time-to-target
  mean 155.7 min. Owner GO 2026-08-28.
- **EM-4D** — Platt-scaling calibration with target-smoothing; min-support
  policy n≥1,000/k≥10 reused verbatim from EM-1c; **all 162 cells
  calibrated, 0 insufficient-support, 0 unstable fits**. Owner GO
  2026-08-28.
- **EM-4E** — sealed FINAL_TEST (157 sessions, 702,702 rows,
  2026-01-01–2026-08-21), structurally sealed evaluation script (no
  sklearn import). Logistic beats deterministic **18/18** on FINAL_TEST
  PR-AUC too (TOUCH_10: 0.211 vs 0.037). TOUCH_10 FINAL_TEST excursion
  (MFE 13.0%, MAE 3.1%, time-to-target 143.2 min) closely matches
  VALIDATION's figures. **Owner-approved / GO 2026-08-28. FINAL_TEST must
  not be read again regardless of any future decision.**

**Default answer for EM-7: NO model change required.** Nothing in EM-7's
documented scope (§6, ADR-012 §10) calls for refitting, recalibration,
tuning, reopening FINAL_TEST, new features, threshold changes, label
changes, or a different Platt support policy — it is explicitly a
*runtime/operational* validation of the already-frozen artifacts, not a
modeling milestone. This discovery found nothing in the roadmap
contradicting that default.

## 6. EM-5 frozen live-capture contract

Track B (Tuesday 2026-09-01): **9 symbols, 9 checkpoints (09:20 through
14:00 IST), 81/81 raw Kite files, 1,768 raw candles, 0 off-grid `ts_open`
values.** Track B.1 added the explicit `NO_OFF_GRID_PROVISIONAL_OBSERVED`
classification (no eligible off-grid rows existed to classify against the
original 3-outcome scheme). Section 14 production canary:
**518/518 mature instruments, 9,324/9,324 all-required-fields-known
(100.0000%), zero provider/network calls, deterministic replay — PASS.**
EM-5 owner-approved/closed 2026-09-01; full suite 2,956 passed at that
point.

EM-7 will consume EM-5's live-scanner infrastructure (`run_scan_cycle`,
the `EmrMarketDataPort` read boundary, the checkpoint reference-price
seam) directly — **EM-5 itself does not need to be rerun** merely because
EM-7 begins.

## 7. EM-6 frozen presentation contract

`presentation.py` (EM-6A): `latest_scan_snapshot`, `top_candidates`,
`top_touch_10_candidates`, `coverage_summary`, `describe_scan_freshness`,
`build_experimental_snapshot`, plus EM-6B's additive
`build_touch_10_radar_snapshot` (one frozen `run_id` for both candidates
and coverage). `GET /api/v1/emr/experimental/touch-10-radar`: READ-only
auth, `AthenaResponse` envelope, one injected request clock (corrected by
EM-6B.1 so `scan_age.as_of == meta.as_of` exactly), existing Market
Intelligence "Experimental" panel, no new top-level navigation, zero
provider calls, zero scanner scheduling, zero canonical coupling.

**EM-6 explicitly did not create a production scanner/scheduler** — its
own discovery doc states this as a boundary: *"EM-6 must... never invoke
`run_scan_cycle` itself, never write to `db/emr.db`, and never gain a
scheduler/production trigger of its own."* `db/emr.db`'s absence at EM-6
closure was explicitly recorded as intentional, not a defect: *"no
scheduler was authorized; not a defect — EM-6 exposes persisted reality
only."* This discovery confirms that fact is **still true today** (§9).

## 8. Current EMR end-to-end pipeline

| Stage | Component | Classification |
|---|---|---|
| Universe selection (live) | `live/market_data_port.py` `resolved_universe()` (ADR-011 named universe, e.g. `athena_core`) | LIVE-CAPABLE BUT UNSCHEDULED |
| Universe selection (research/canary) | `live/canary_gate.py` `select_mature_history_instruments()` | RESEARCH ONLY |
| Market-data input | `live/market_data_port.py` `SqliteEmrMarketDataAdapter.candles_for_instruments()` — reads `db/athena.db` | LIVE-CAPABLE BUT UNSCHEDULED |
| Checkpoint reference price (live seam) | `live/checkpoint_reference_price.py` `collect_checkpoint_reference_prices()` | LIVE-CAPABLE BUT UNSCHEDULED (real Kite `/quote` call) |
| Feature/evidence construction | `live/evidence_assembly.py` `assemble_candidate_row()` | LIVE-CAPABLE BUT UNSCHEDULED |
| Deterministic score (EM-4A) | `deterministic_score.py` / `live/deterministic_scoring.py` | LIVE-CAPABLE BUT UNSCHEDULED |
| Model inference (EM-4B) | `live/frozen_inference.py` `load_frozen_model()`/`score()` | LIVE-CAPABLE BUT UNSCHEDULED |
| Calibration (EM-4D) | `em4d_calibration.py` `apply_platt_scaling()` | LIVE-CAPABLE BUT UNSCHEDULED |
| Candidate state machine | `live/state_machine.py` `determine_next_state()` | LIVE-CAPABLE BUT UNSCHEDULED |
| TOUCH-10 ranking | `live/ranking.py` `rank_candidates()` | LIVE-CAPABLE BUT UNSCHEDULED |
| Scan persistence | `store/repository.py` `save_scan_run/save_candidates/save_transitions` | PERSISTED (tests/canary only) |
| Checkpoint/freshness | `live/presentation.py` `describe_scan_freshness()` | READ-ONLY PRESENTATION |
| Coverage | `live/presentation.py` `coverage_summary()` | READ-ONLY PRESENTATION |
| Presentation | `live/presentation.py` (whole file) | READ-ONLY PRESENTATION |
| API | `api/v1/routers/emr.py` | PRODUCTION-ACTIVE as a route (mounted, live), but only ever reads an empty state today |
| Dashboard | `09b-emr-experimental.js`/`06b-emr-experimental.css` | READ-ONLY PRESENTATION |
| **Scanner orchestrator** | `live/scanner.py` `run_scan_cycle()` | **LIVE-CAPABLE BUT UNSCHEDULED — zero non-test/non-canary callers anywhere** |
| Production canary | `live/canary_gate.py` `run_em5_production_canary()` | OFFLINE (zero Kite calls by design) |

**Nothing in `explosive_move/` is production-active in the sense of
"wired into a currently-running scheduled path."** The API route is
mounted and live, but structurally can only ever return the empty state
until something writes to `db/emr.db`.

## 9. Current production/runtime state

Verified directly (filesystem/config/scheduler inspection, no provider
calls, no DB writes):

- `db/emr.db` **does not exist** — confirmed via `ls db/` (only
  `athena.db`, `darvax.db`, and their `-shm`/`-wal` files present).
- No scheduler/cron wiring anywhere references `explosive_move`/`emr` —
  `src/athena/scheduling/`, `src/athena/ops/`, launchd plists, and
  `.github/workflows` all confirmed clean.
- **No CLI command exists at all** for EMR scanning — `src/athena/cli.py`
  has zero EMR subcommands. Today there is nothing even manual to run;
  `run_scan_cycle` is callable only from a Python REPL/test.
- `config/emr/` contains only `frozen_models/v1/` (model artifacts) — no
  `config/emr.json`-style enable/disable gate exists, unlike DarvaX's
  `config/darvax.json`'s `enabled` flag.
- 40 test files under `tests/explosive_move/` plus 3 more elsewhere; no
  production-scheduling integration test exists (consistent with there
  being nothing to test yet).

This confirms EM-6's own closure statement remains accurate today: no
EMR scanner scheduler exists, `db/emr.db` absence is not a defect.

## 10. Actual EM-7 roadmap definition

Extracted verbatim from the only two documents that give EM-7 real
content (ADR-012 §10, quoted in full in §4 above, and the roadmap doc):

`docs/design/ATHENA-EXPLOSIVE-MOVE-RADAR-ROADMAP.md`, "EM-7 — Live shadow
validation": *"Run without affecting ATHENA. Track precision, lift,
calibration, MFE, MAE, misses, false positives, regime drift, data
failures, and latency. Compare EMR disabled with EMR shadow mode for
dashboard load time, symbol-validation latency, canonical cycle timing,
database query latency and volume, CPU and memory use, and EMR
scanner-cycle duration. Any material canonical regression blocks
promotion."*

The two documents do not conflict — the roadmap doc is essentially a
restatement of ADR-012 §10. **There is no discrepancy to reconcile; there
is simply nothing more specific written down anywhere.** No operational
mechanism, no checkpoint cadence for continuous live operation, no
universe scope for the shadow run, no acceptance threshold for "material
regression," and no shadow-run duration/sample-size requirement exist in
any document. Every other reference to EM-7 across `docs/MILESTONES.md`,
`docs/ATHENA-EMR-HANDOFF.md`, `IMPLEMENTATION_SUMMARY.md`,
`docs/design/EM-5-LIVE-SCANNER-CONTRACT.md`, and
`docs/design/EM-6B-EXPERIMENTAL-RADAR-UI-CONTRACT.md` is a bare
not-started/boundary marker (e.g. "Do not start EM-7... until explicitly
authorized"), never additional scope. **Treat nothing beyond the two
quotes above as authoritative EM-7 content.**

## 11. Gap after EM-6

The actual, source-confirmed gap is not modeling, not presentation, and
not data acquisition (all three are solved). It is entirely
**operational invocation**:

1. **No live-invocation mechanism of any kind** — no CLI command, no
   scheduler, no cron entry (§9).
2. **The scanner is not yet safe to run unattended** — three real
   correctness gaps (§16, §17): no exception handling / no `FAILED`/
   `PARTIAL` run status; non-idempotent candidate/transition persistence;
   no concurrency lock.
3. **No config-driven enable/disable gate** exists to make an
   "EMR-disabled vs. EMR-shadow-mode" comparison a clean, reversible
   toggle (DarvaX has exactly this pattern already, at
   `config/darvax.json`'s `enabled` flag — EMR has no analogue).
4. **No owner-frozen checkpoint cadence for continuous live operation** —
   the 9-checkpoint list exists (§14) but is a convention followed by
   test/canary callers, not enforced or scheduled anywhere.

None of these are hypothetical improvements — every one is a concrete,
cited absence blocking the documented EM-7 objective from being
attempted at all.

## 12. Scanner/orchestrator finding

`run_scan_cycle()` (`src/athena/explosive_move/live/scanner.py`) has
exactly two non-test/non-definition call sites in the entire repository:
the offline canary (`live/canary_gate.py`, itself only invoked from a
test) and `tests/explosive_move/test_em5_scanner.py`. It takes a fully
caller-supplied `ScanCycleConfig` (universe, session_date, checkpoint,
checkpoint_instant, session_open_time, model_version) plus an injected
`EmrMarketDataPort`, `EmrRepository`, and a `collect_checkpoint_prices`
callable. It reads market data exclusively through the read-only port
(§8), writing only to the isolated `EmrRepository`. `run_id` is
deterministically derived from `(session_date, checkpoint, universe,
model_version)` via SHA256 — replaying identical inputs produces the
identical `run_id`, but (§17) that does not make persistence itself
idempotent. `regime_lookup` defaults to `lambda _d: None` unless a caller
explicitly wires `regime_source.build_canonical_regime_lookup` — a naive
future scheduler invocation would silently get all-`UNKNOWN` regime
fields unless this is wired deliberately.

## 13. Scheduler finding

None exists (§9, §11). ATHENA's own canonical scheduler
(`DryRunCycleOrchestrator`/`HostDueRunner`/`CycleWorker`, the same
infrastructure ID-7P0 just instrumented) is a plausible architectural
precedent to study, but nothing in `explosive_move/` reuses or references
it today. DarvaX's own opt-in satellite pattern (config-gated `enabled`
flag, mounted via `api/darvax_mount.py`) is the closer isolation
precedent, though this discovery did not audit whether DarvaX itself runs
on any independent schedule — worth a follow-up look before EM-7A0 if the
owner wants that precedent studied in more depth.

## 14. Checkpoint-policy finding

Hardcoded, not config-driven: `CANDIDATE_CHECKPOINTS_IST` in
`src/athena/explosive_move/contracts.py` and the independently-defined,
identical `TRACK_B_CHECKPOINT_SCHEDULE` in
`src/athena/data/live_m5_provisional_settlement_diagnostic.py` both list
the same 9 IST times: `09:20, 09:30, 09:45, 10:00, 10:30, 11:00, 12:00,
13:00, 14:00`. This is the schedule EM-5's Track B live capture and the
production canary both used. **`run_scan_cycle` itself does not enforce
this list** — `ScanCycleConfig.checkpoint` is a bare caller-supplied
string with no enumeration guard inside the function. EM-6 presentation
code has no checkpoint-list assumption at all (treats it as an opaque
persisted column). **A production checkpoint schedule for continuous
shadow operation is not invented here** — it is an explicit owner
question (§29).

## 15. Universe-policy finding

Live scanner path: a mandatory, caller-supplied ADR-011 named universe
(e.g. `athena_core`), resolved via the same named-universe mechanism used
ATHENA-wide (`config/universes.json`) — no hardcoded universe inside
`explosive_move/`, and no additional maturity/liquidity filter applied by
`run_scan_cycle` itself. Research/canary path layers an *additional*,
EMR-specific "mature-history" filter (≥50 admitted daily bars) used only
for canary completeness checks, never by the live scanner's own
candidate scoring. **This is a real divergence a shadow run must resolve
explicitly** (§29) — running the full unfiltered universe vs. the
mature-history subset would produce different candidate populations and
different canonical-load characteristics.

## 16. Data-acquisition finding

Already solved, cleanly. `EmrMarketDataPort`/`SqliteEmrMarketDataAdapter`
(`live/market_data_port.py`) is a narrow, read-only Protocol
(`list_instruments`, `resolved_universe`, `candles_for_instruments`)
wrapping ATHENA's canonical `SqliteRepository`, deliberately mirroring
DarvaX's own ADR-010 read-port pattern (stated explicitly in the module's
own comments). The only network call anywhere in the pipeline is one
authorized, narrow, batched Kite `/quote` seam
(`checkpoint_reference_price.py`) for the checkpoint reference price —
everything else reads already-ingested candles. **An operational EMR
scanner would not duplicate ATHENA's own candle-ingestion provider
traffic** — it reads what's already there. The one live quote call per
checkpoint per instrument is the only new provider-traffic surface EM-7
would introduce, and it is already narrowly scoped and pre-existing
(built in EM-5, not new).

## 17. Provider-traffic implication

Given §16, EM-7 does not need to (and should not) couple to or duplicate
ID-7P0's own ingestion path — the two tracks read the same underlying
canonical candle data through entirely separate, already-isolated
mechanisms (ID-7P0 instruments the ingestion that *writes* it; EMR only
*reads* it afterward, never re-fetching). No ID-track code was touched by
this discovery, per instruction. The one incremental provider-traffic
cost of operationalizing EMR is the per-checkpoint batched quote call
already built and already rate-limit-paced under the `quote` endpoint
class (per the ID-7P0.1 provider audit, `quote_min_interval_seconds=1.0`)
— a small, already-understood, already-isolated addition, not a new
unknown cost.

## 18. Provisionality/finality finding

EMR does not currently borrow ADR-013's State/Finality/Confirmation
vocabulary, and this discovery does not recommend it do so automatically
— EMR already has its own domain semantics: a per-candidate
`data_freshness` flag (`"FRESH"`/`"STALE"`, driven by a caller-supplied
`max_staleness_minutes` threshold, computed by the scanner itself at scan
time — a candle-staleness concept) is explicitly distinct from the
viewer-relative "scan age" concept EM-6's `describe_scan_freshness`
exposes (a pure elapsed-time fact, no threshold, no FRESH/STALE label).
Neither table currently persists an explicit "settlement status" or
"model/calibration version" column beyond `model_version` already
threaded through `ScanCycleConfig`/persisted per candidate. **Whether
EM-7 needs a more explicit finality/provenance contract is left as an
open, evidence-based question for EM-7A0**, not decided here — EMR's own
vocabulary should be used if one is needed, not ADR-013's borrowed
wholesale.

## 19. Database-lifecycle finding

Schema version 1 (`store/schema.py`, `EMR_SCHEMA_VERSION = 1`); tables
`emr_schema_version`, `emr_scan_runs`, `emr_candidates`, `emr_transitions`.
`EmrRepository.initialize()` is idempotent (`CREATE TABLE IF NOT EXISTS`)
but **never called automatically** — merely instantiating
`EmrRepository(path)` performs no I/O; the file is created lazily on
first `initialize()`/`save_*` call. Path resolution:
`ATHENA_EMR_DB_PATH` env override, else `<repo_root>/db/emr.db`. No
migration script beyond a bare version-number bump exists (only version 1
is defined — a real future gap if schema ever needs to change). No
retention/cleanup/TTL logic anywhere. No EMR-specific integrity-check
tooling (only frozen-model-artifact SHA256 verification, a different
concern). Read/write separation is structural: `EmrRepository` opens a
normal read-write WAL connection; `live/presentation.py` opens a
genuinely separate `mode=ro` + `PRAGMA query_only=ON` connection. **Why
`db/emr.db` doesn't exist today**: the only code path that writes to it
(`run_scan_cycle` via `EmrRepository.save_*`) is never invoked outside
tests, and tests always use `tmp_path` fixtures, never the real default
path. If EM-7 causes its creation in production, that is exactly the
kind of explicit operational boundary this discovery flags for owner
approval (§29) — not something to be created here.

## 20. Run-lifecycle/idempotency finding

`emr_scan_runs.status` is a bare string, not an enum — only three literal
values are ever written: `"RUNNING"`, `"SKIPPED_SESSION_TYPE"`,
`"COMPLETE"`. **No `FAILED` or `PARTIAL` status exists anywhere in the
domain model.** `run_scan_cycle` has zero `try`/`except` blocks — an
unhandled exception mid-scan (e.g. a missing Platt calibration entry)
propagates uncaught, leaving that run's row **permanently stuck at
`RUNNING`** with zero candidate/transition rows ever persisted (both
`save_candidates`/`save_transitions` are called exactly once, after the
full per-instrument loop completes). Missing provider data for a specific
instrument is handled gracefully (that instrument is silently excluded,
not marked failed). **Persistence is not idempotent**: `save_candidates`/
`save_transitions` are plain inserts with no unique constraint —
replaying the identical deterministic `run_id` duplicates every row for
that run (confirmed: no test exercises replay-into-the-same-repo, only
independent-repo score-equality). No concurrency lock exists anywhere in
`EmrRepository` beyond an in-process `threading.RLock` (no cross-process
protection) — not reachable today given zero scheduling exists, but a
structural gap if it ever were wired.

## 21. Freshness finding

Confirmed exactly as EM-6A/EM-6B specified and preserved unmodified:
`describe_scan_freshness()` is pure, takes `as_of` explicitly, computes
`age_seconds`/`age_minutes` only — **no FRESH/STALE threshold exists
anywhere in `explosive_move/`** (confirmed by repo-wide grep). Separately,
`EmrCandidateView.data_freshness` (a different, candle-staleness concept
computed by the scanner at scan time from a caller-supplied
`max_staleness_minutes`) is not a scan-age threshold either — it's a
pre-existing boolean the scanner already computed. **This discovery does
not invent a stale-after duration for anything** — if EM-7's
operationalization genuinely needs a scheduling/UI-availability freshness
policy, that is an explicit gap to resolve later (§29 candidate), not
decided here.

## 22. TOUCH-10 methodology finding

Frozen and unchanged. `EventFamily.TOUCH` + `threshold_percent=10`;
"touch" means the session's high reaches
`prior_close × 1.10` at any qualifying 5-minute candle
(`event_labels.py` `evaluate_touch_label()`). Ranking is computed once at
scan time by the frozen EM-4C tie-break rule (calibrated probability
descending, instrument_id ascending on ties) over the EM-4B+EM-4D
calibrated score; `top_touch_10_candidates()` applies no additional
probability/score threshold beyond the caller-supplied `limit`. The
`probability_language` field honestly distinguishes
`"calibrated_probability"` from `"raw_estimate"` when Platt calibration
lacked minimum support. Explicit disclaimers exist
(`EXPERIMENTAL_LABEL = "Experimental research signal -- not a trade
recommendation"`; module docstring bans `BUY`/`SELL`/`stop`/`target`/
canonical `confidence` language). **No literal "not a probability of
profit" prose string exists anywhere in `explosive_move/`** — noted as a
minor honest gap, not a defect requiring action here. **Verified: EM-7
should operationalize this exact frozen semantics, not redefine
TOUCH-10** — nothing in either EM-7 source document proposes any
methodology change, and this discovery found no reason one would be
needed.

## 23. Operational-validation requirement

What would be needed before an operational EMR scanner could be trusted
to run unattended (derived from §11's actual gaps, not invented):
scheduler correctness (does the cadence fire as configured, exactly
once, per checkpoint); the three scanner-correctness fixes (§20) —
explicit `FAILED`/`PARTIAL` states, idempotent persistence, a
concurrency lock; provider-call completeness (does the checkpoint quote
seam fail gracefully); run completeness (does a scan cover the intended
universe every time); database integrity (no orphaned rows, no
duplicate candidates); freshness (scan-age is reported honestly);
failure recovery (a crashed run doesn't corrupt or block the next one);
UI coherence (the existing empty/populated states continue behaving
correctly once real data exists); zero canonical coupling (re-verify
ADR-012 isolation after any new worker code lands). **Explicitly
excluded from this list, per instruction: outcome/profitability
validation — EM-4 already owns model-performance validation (§5); EM-7's
own documented purpose (§10) is operational + statistical-health
shadow tracking, not a new profitability study.**

## 24. Observability requirement

Minimal, not over-designed: run started/completed/failed, checkpoint,
instrument count, coverage, candidate count, TOUCH-10 count, elapsed
time, provider failures, persistence failures — the same shape EM-6's
own presentation layer already surfaces for completed scans, extended
only with the currently-missing failure/duration facts a scheduler would
need. No new observability platform is proposed; ATHENA's existing
`observability/` conventions (including ID-7P0's own orthogonal timing
pattern) are the natural precedent to reuse if/when this is built.

## 25. Empty/failure-state semantics

EM-6 already handles "database absent" and "no COMPLETE scan" honestly
(§7). Not yet handled anywhere, because they cannot occur yet given §20's
findings: "latest scan failed" (no `FAILED` status exists to detect),
"latest scan partial" (no `PARTIAL` status exists), "current checkpoint
missing" (no checkpoint-completeness tracking exists). **These are
presentation-semantics gaps that are a direct downstream consequence of
§20's run-lifecycle gap** — recommending run-lifecycle semantics only
(§20), not a UI redesign, per instruction. An old successful scan should
never be presented without its own age/run information — EM-6 already
does this correctly (`scan_age` is always attached); this principle
should simply continue to hold once failure states exist to represent.

## 26. Security/authorization finding

The existing EM-6 API surface remains exactly READ-only: one `GET` route,
`RequirePermission(Permission.READ)`, zero mutation endpoints (confirmed
by grep — no POST/PUT/PATCH/DELETE under the `/emr` prefix). If EM-7
needs manual operational controls ("run scan now", "retry scan"), this
discovery recommends **against** adding a mutation API endpoint for
that — prefer a scheduler/CLI operational boundary (matching how
ATHENA's own canonical cycles are triggered via `athena run-due`/
`serve --with-cycles`, not via a dashboard "run cycle" button). No
endpoint is added here.

## 27. ADR-012 isolation proof

Automated coverage: `tests/explosive_move/test_em5_isolation.py` runs
real AST-based import scans, but its `_FORBIDDEN_CANONICAL_IMPORTS` list
covers `decision`/`risk`/`portfolio`/`orders`/`execution`/`orchestration`
— it does **not** currently check `scoring`/`confidence`/`intraday`/
`darvax` in the `explosive_move → canonical` direction (only the reverse
direction, for a narrower canonical-package list, is checked). Manual
verification for this discovery, covering the full requested list
(`decision`, `scoring`, `confidence`, `risk`, `portfolio`, `intraday`,
`darvax`, canonical `SqliteRepository`): **zero occurrences of the first
seven anywhere under `src/athena/explosive_move/`.** `SqliteRepository`
is imported in exactly two places — `live/market_data_port.py` (the
already-discussed, structurally read-only market-data port, §16) and
`em1r2_materialize.py` (an offline, `argparse`-driven research
materialization CLI script, not part of any live path). Neither writes
to `db/athena.db`; both are intentional, narrow, and already documented.
**No violation found** — but the isolation test suite has a real scope
gap (doesn't check `scoring`/`confidence`/`intraday`/`darvax` imports
from `explosive_move`, and doesn't check `SqliteRepository` at all) worth
closing in a future hardening slice, reported honestly rather than
glossed over.

**Every recommended EM-7 direction in this document preserves:** EMR DB
isolation (own file, own schema, never touches `db/athena.db` for
writes); EMR domain isolation (no canonical package imports); no
ScoringEngine/Confidence/Risk/Decision/TradePlan/EntryQualification/
Portfolio/DarvaX mutation of any kind (none of these packages appear
anywhere in `explosive_move/`, confirmed above). Any option that would
violate this is rejected outright (§28).

## 28. Architecture options considered

**Option A — Independent, isolated EMR scheduled worker.** A new,
separate invocation mechanism (its own thread/process or a new CLI
command plus an external cron/launchd entry) that calls `run_scan_cycle`
on a defined cadence, writing only to `db/emr.db`, reading market data
through the already-existing `EmrMarketDataPort` (§16 — no duplicate
provider traffic), with its own concurrency lock, and a config-driven
enable/disable gate mirroring DarvaX's `config.enabled` pattern. **This
is the only option evidence directly supports as clean.**

**Option B — EMR stage attached to the canonical ATHENA cycle.** Add
EMR's scan as another step inside `OwnerValidationPipeline`/
`DryRunCycleOrchestrator`'s existing scheduled loop, writing only
isolated EMR artifacts. **Rejected.** This would inject `run_scan_cycle`'s
own reliability gaps (§20 — zero exception handling, no `FAILED` state)
directly into the canonical cycle's own execution path — an unhandled
EMR exception could interrupt canonical Decision/EntryQualification
processing for that cycle, which is exactly the kind of "canonical blast
radius" ADR-012 §10 requires be *measured*, not risked by construction
before it's even measured. It also blurs the "isolated satellite"
pattern ADR-012/ADR-010 both established, even though DB writes would
stay isolated.

**Option C — Independent schedule/process consuming already-persisted
canonical data.** In this codebase, this is not materially different
from Option A — the read-only port already exists and already does
exactly this; "Option C" collapses into Option A once the actual source
state is accounted for.

**Option D — another evidence-supported architecture.** None found.

## 29. Recommended architecture

**Option A**, evaluated against the requested criteria:

- **ADR-012 isolation**: preserved exactly — own DB, own schema, no new
  canonical import, no new provider client beyond the already-authorized
  seam.
- **Provider traffic**: no duplication (§16-17); the one live quote call
  per checkpoint is pre-existing, narrow, and already rate-limit-paced.
- **Checkpoint determinism**: unaffected — `run_scan_cycle`'s own
  determinism (deterministic `run_id`, no internal clock reads) is
  untouched by how it's invoked.
- **Operational complexity**: the smallest option that actually achieves
  "run without affecting ATHENA" — no changes to canonical scheduler code
  at all.
- **Failure isolation**: complete — a crashed EMR worker cannot touch
  canonical cycles, by construction (separate process/thread, separate
  DB).
- **Database ownership**: unchanged, already-isolated.
- **Scheduler ownership**: new and isolated — never shared with the
  canonical scheduler, satisfying the EMR-disabled-vs-shadow-mode
  comparison ADR-012 §10 requires (the toggle is literally "worker
  running" vs. "worker not running", with zero canonical-scheduler
  involvement either way).
- **Replayability**: preserved — `run_scan_cycle`'s own determinism
  already supports it; only the invocation wrapper is new.
- **Observability**: needs the additions in §24, independent of which
  option is chosen.
- **UI freshness**: unaffected — EM-6's presentation layer already
  handles this correctly regardless of how data arrives.
- **Canonical blast radius**: the entire point of ADR-012 §10's
  measurement requirement — Option A is the only option that lets that
  measurement be taken meaningfully (compare "worker off" vs "worker on"
  cleanly), rather than being structurally unmeasurable as in Option B.

This is a recommendation for future ADR/owner ratification, not a
self-executed architecture change — nothing has been built.

## 30. ADR requirement

**A new ADR (or an ADR-012 amendment) is recommended.** ADR-012 itself
anticipated EM-8 needing "a separate ADR for canonical integration," but
did not originally contemplate EM-7 introducing a *new production
worker/scheduler* — even one that remains fully isolated. Per this
repository's own established convention (CLAUDE.md's "new architectural
boundary → ADR" principle; ADR-013's own stated trigger criteria — "a new
persisted decision-relevant concept, a new live workflow stage, and a
new architectural boundary"), Option A meets an analogous bar: a new
scheduled worker, new production DB-lifecycle activation, and a new
provider-access-timing boundary (even though the provider call itself is
pre-existing) are all genuinely new operational facts about the system.
**No ADR is drafted here** — recommendation only, per instruction and
absent any documented convention authorizing discovery itself to draft a
PROPOSED ADR.

## 31. Proposed EM-7 sub-milestones

Derived from the actual gaps in §11-20, not assumed from the owner's own
example shape (though it turns out closely aligned):

- **EM-7A0** — Architecture/operational contract (ADR or ADR-012
  amendment): formalize Option A's boundary — isolated worker, own lock,
  config-gated enable/disable, checkpoint cadence, universe scope. No
  code.
- **EM-7A** — Scanner correctness hardening: explicit `FAILED`/`PARTIAL`
  run states + exception handling in `run_scan_cycle`; idempotent
  candidate/transition persistence (a uniqueness key or `ON CONFLICT`);
  a concurrency lock; explicit `regime_lookup` wiring requirement. This
  is prerequisite engineering hygiene, not shadow validation itself —
  distinguishing it from the owner's example "EM-7A scanner
  orchestration" naming, since orchestration doesn't yet exist to
  harden — hardening the *engine* comes first.
- **EM-7B** — Scheduling/checkpoint-cadence wiring: the actual invocation
  mechanism (isolated worker thread or CLI + cron), config-driven
  enable/disable, on the owner-frozen checkpoint schedule from §29's
  owner questions.
- **EM-7C** — Production EMR DB activation: first real `db/emr.db`
  creation via the new scheduled path, safety-verified (mirrors ID-6E.2's
  precedent — integrity-checked, checksummed backup discipline).
- **EM-7D** — Shadow/live operational canary: the actual EM-7 core ask —
  EMR-disabled vs. EMR-shadow-mode canonical performance comparison
  (ADR-012 §10's exact measurement list) plus statistical-health
  tracking (precision, lift, calibration, MFE, MAE, misses, false
  positives, regime drift, data failures, latency) over a real shadow
  run.
- **EM-7E** — Unattended validation / owner review: confirm the shadow
  operation has run cleanly for a sufficient period, then hand the
  promote/continue/retire decision to EM-8.

No sub-milestone is authorized by this discovery. The existing roadmap
(`docs/MILESTONES.md`, ADR-012, the roadmap doc) does not define EM-7
sub-milestones itself — nothing to reconcile against beyond the single
EM-7 line.

## 32. EM-8 boundary

EM-8, like EM-7, has no real contract beyond a four-way decision menu:
*"Decide research-only, continued shadow, retirement, or a new
integration ADR."* ADR-012's only constraint: *"EM-8 requires owner
approval and a separate ADR for canonical integration."* No design doc,
no evaluation criteria, no sub-milestone breakdown exists anywhere for
EM-8. **This EM-7 recommendation does not implement any part of EM-8** —
it stops at "shadow operation validated," explicitly leaving the
promote/retire/continue-shadow/integrate decision itself, and any
canonical-integration architecture, to EM-8's own future authorization.
No detailed EM-8 contract is invented here merely to look complete.

## 33. Owner decisions required

Kept small — only genuine policy questions this discovery cannot answer
from source.

---

**Question 1 — What checkpoint cadence should EM-7's live shadow
operation actually use?**

*Why it matters*: the 9-checkpoint schedule (§14) is a research/canary
convention, not enforced anywhere in `run_scan_cycle`. Continuous
unattended operation needs an owner-frozen cadence.

*Options*: (a) reuse the existing 9-checkpoint schedule as-is (already
validated by EM-5 Track B); (b) align to ATHENA's own 15-minute REFRESH
cadence instead; (c) a different owner-specified schedule.

*Agent recommendation*: (a) — it's already validated end-to-end by
EM-5's real live capture, requires no new research, and keeps EM-7
focused on operationalizing what's proven rather than also re-validating
a new cadence.

*Consequence*: (a) is the smallest, best-evidenced choice but doesn't
align with ATHENA's own cycle timing (may complicate any future shared-
infrastructure question); (b)/(c) would need fresh evidence before
being trusted.

---

**Question 2 — What universe should EM-7's shadow run score?**

*Why it matters*: §15 found a real divergence — the live scanner
defaults to the full resolved ADR-011 universe unfiltered, while the
research/canary path uses a narrower "mature instruments" subset. These
produce materially different candidate populations and different
canonical-load profiles (directly relevant to ADR-012 §10's own
performance-comparison requirement).

*Options*: (a) full resolved universe (matches `run_scan_cycle`'s
existing default, no new filter code); (b) the mature-history subset
(matches what's already been canary-tested); (c) a new, explicitly
EM-7-scoped universe.

*Agent recommendation*: (b) — reuses an already-proven-safe filter
(the same one the Section 14 canary validated at 100% field-known rate)
rather than the untested full universe, and keeps the shadow run's
canonical-load footprint closer to what's already been measured.

*Consequence*: (b) is well-evidenced but narrower coverage than the
full universe; (a) tests the true production shape but with zero prior
canary evidence on it; (c) adds new scope this discovery doesn't
recommend.

---

**Question 3 — Should scanner correctness hardening (EM-7A) be its own
gated sub-milestone, or bundled into scheduling (EM-7B)?**

*Why it matters*: §20's three gaps (no `FAILED`/`PARTIAL` states,
non-idempotent persistence, no lock) are real engineering debt
independent of any scheduling decision — but splitting them into their
own milestone adds review overhead.

*Options*: (a) EM-7A as its own gated milestone before scheduling exists
at all; (b) bundle hardening into EM-7B's own implementation.

*Agent recommendation*: (a) — these are correctness fixes to
already-existing, already-tested code with no scheduling dependency;
reviewing them in isolation (smaller diff, clearer test story) is safer
than reviewing them mixed with new scheduler code.

*Consequence*: (a) adds one more review checkpoint; (b) is faster but
risks a larger, harder-to-review diff conflating "is the engine correct"
with "does the scheduler work."

---

**Question 4 — What should the config-driven enable/disable gate look
like?**

*Why it matters*: no such gate exists in EMR today (§9, §11), and it's
the mechanism ADR-012 §10's EMR-disabled-vs-shadow-mode comparison
depends on being clean and reversible.

*Options*: (a) mirror DarvaX's exact pattern (`config/darvax.json`'s
`enabled` flag, read once at mount/start time); (b) a different
mechanism (env var, database flag, etc.).

*Agent recommendation*: (a) — it's an already-proven, already-reviewed
pattern in this exact codebase for exactly this kind of isolated
satellite capability; no reason to invent a new mechanism.

*Consequence*: (a) is fast and consistent with precedent; (b) would need
its own design/review with no compensating benefit identified.

---

**Question 5 — Should the isolated worker reuse or mirror ATHENA's own
`CycleWorker` pattern (the same infrastructure ID-7P0 just instrumented),
or be something simpler?**

*Why it matters*: `CycleWorker` (`src/athena/ops/serve_runtime.py`) is a
proven, tested, already-running background-thread-with-flock-lock
pattern — but reusing/importing from `ops/` could create an unwanted
coupling direction (EMR depending on canonical `ops/` code) that ADR-012
did not originally contemplate either way.

*Options*: (a) write a structurally-similar but fully independent worker
inside `explosive_move/` (no import from `ops/`); (b) directly reuse/
extend `CycleWorker`; (c) a simpler mechanism (e.g. a cron-invoked CLI
command with no persistent background thread).

*Agent recommendation*: (a) — preserves ADR-012's directional isolation
guarantee cleanly (no dependency edge from EMR into canonical `ops/`),
at the cost of some duplicated (small, well-understood) locking code.

*Consequence*: (a) keeps isolation unambiguous but duplicates ~50 lines
of proven pattern; (b) risks a real, new coupling direction; (c) is
simplest operationally but loses the "continuously running, always
polling" property a true shadow validation arguably wants.

## 34. Risks

- **Building on an already-known-unsafe scanner** if EM-7B proceeds
  before EM-7A's hardening (§20) — an unhandled crash mid-scan today
  leaves silent, permanent `RUNNING` rows with no failure signal.
- **Duplicate-row corruption** if any shadow run is ever retried/replayed
  before EM-7A's idempotency fix lands.
- **Canonical blast radius risk** if Option B (rejected, §28) were chosen
  instead of Option A — injecting EMR's current reliability gaps directly
  into the canonical cycle.
- **Isolation-test scope gap** (§27) — the existing automated isolation
  test doesn't check `scoring`/`confidence`/`intraday`/`darvax` imports
  from `explosive_move`, nor `SqliteRepository` at all; a future change
  could introduce a real violation without the existing test catching it.
- **Universe/checkpoint choices made without evidence** if Questions 1-2
  are decided casually rather than deliberately, given ADR-012 §10's own
  measurement requirement depends on a stable, well-understood shadow
  population.
- **EM-8 scope creep** if EM-7 quietly grows integration-adjacent
  features (e.g. any canonical-facing UI/API beyond the existing
  Experimental panel) — explicitly guarded against in this document
  (§32).

## 35. Final recommendation

Proceed with **Option A** (an isolated, config-gated EMR scheduled
worker, reusing the already-existing read-only market-data port,
writing only to EMR's own DB) as the recommended direction for a future
EM-7A0 architecture contract — pending owner resolution of the 5
questions in §33, particularly Questions 1-2 (cadence and universe),
which materially shape what EM-7A0's contract should actually specify.
No implementation is recommended to start immediately. The smallest safe
next step, if the owner agrees with this direction, is **EM-7A0** — an
architecture/ADR contract only, no code — followed by **EM-7A**'s
scanner-correctness hardening before any scheduling work begins.
