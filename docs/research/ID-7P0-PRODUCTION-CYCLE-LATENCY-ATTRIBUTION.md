# ID-7P0 — Production Cycle Latency Attribution

**Status:** `ID-7P0 INSTRUMENTATION LIVE — NATURAL EVIDENCE ACCUMULATION
ACTIVE`. Instrumentation implemented, tested, Ruff-clean, timing-boundary
corrected (ID-7P0.1, owner-approved/closed), and — following an
owner-authorized, safety-verified production restart on 2026-09-03 (no
active cycle interrupted; zero artificial runs/provider calls/Decisions/
EntryQualification rows created by the restart itself; PID 17344 → 93626)
— now **live** in the running `athena serve --with-cycles` process.
Natural REGULAR-cycle evidence accumulation is active; the next expected
evidence session is 2026-09-04. Owner has instructed a wait state: no
further ID-7 action until explicitly resumed for a read-only evidence
audit.

## 1. Why this milestone exists

ID-6E established genuine production latency (`persisted_at - as_of`
median ≈9.38 min, p90 ≈588.42s, p95 ≈592.52s, max ≈622.71s). ID-7
discovery then found `entry_qualification` writes cluster in the final
~5-7 seconds of each ~550-560s cycle, producing the working hypothesis
`dominant latency ≈ ingestion before the analytical scan`. This document
replaces that hypothesis with measurement infrastructure and — from a
newly-audited provider constraint (§6) — a concrete, quantitative,
partial explanation obtained *before* any single natural cycle has even
run under the new instrumentation.

## 2. Instrumentation architecture

New module: `src/athena/observability/timing.py` — `CycleTimingRecorder`
(phase-level wall-clock spans via a context manager) and `CallTimings`
(per-call durations reduced to median/p90/p95/max/slowest-N before ever
being exposed — individual per-instrument samples are never persisted or
logged). Both are pure, dependency-free, and take an injectable `clock:
Callable[[], float]` (default `time.monotonic`).

**Deliberately orthogonal to `WorkflowEngine`'s own deterministic
per-stage `_MonoClock`** (`src/athena/ops/owner_validation.py:50-56`) —
that clock exists purely for business-replay determinism and is untouched
by this module; `owner_validation.py` was not modified anywhere by this
milestone.

Wired in two places:

- **`LiveIngestionEngine.run_cycle`** (`src/athena/data/ingestion/engine.py`)
  gained an optional `timing: CycleTimingRecorder | None = None` keyword
  argument (default preserves the exact prior signature/behavior). When
  provided, each of the three provider-call sites — the sequential daily
  loop, the sequential intraday loop, and the single quotes batch call —
  records its own call duration into named groups
  (`ingestion.daily_candles`, `ingestion.intraday_candles`,
  `ingestion.quotes`), including on failure (a `try/except` around each
  call records the failed duration with `ok=False` before re-raising the
  original exception unchanged).
- **`DryRunCycleOrchestrator.run_cycle`** (`src/athena/scheduling/dry_run.py`)
  gained an optional `enable_timing: bool = False` constructor flag
  (default preserves exact prior behavior; existing test doubles that
  don't accept a `timing=` kwarg are never called with one). When enabled,
  it reuses its **own already-existing real monotonic clock**
  (`self._clock`, already `time.monotonic` by default — no new clock was
  introduced) to wrap the ingestion call in an `ingestion_total` phase and
  the pipeline (`OwnerValidationPipeline.run`, the whole 11-stage/
  528-instrument analytical scan) call in a `scan_total` phase. A residual
  phase, `orchestration_overhead_pre_final_persist`, is derived as
  `duration - ingestion_total - scan_total`, where `duration` is the
  pre-existing `self._clock() - t0` measurement this class already took
  (§2.1) — safe because the two wrapped phases are sequential and
  non-overlapping within the same `try` block, so this arithmetic
  double-counts nothing. **Important boundary correction (ID-7P0.1):**
  `duration` is captured *before* the final COMPLETED/FAILED `RunRecord`
  is persisted (`self._repo.save_run(final, detail=detail)` runs strictly
  after). The residual therefore covers the initial RUNNING `save_run`,
  `RunRecord`/`detail` construction, and error handling that precede the
  final write — it does **not** include the final `save_run` call itself.
  This is deliberate: adding a second write, or reordering the existing
  write, purely to make the residual "complete" would make the
  instrumentation change the operational behavior it is trying to
  measure, which the owner's own instruction explicitly rejects. The name
  reflects this bounded scope rather than a generic "finalization".

### 2.1. Why `duration_seconds` itself is unaffected

`DryRunCycleResult.duration_seconds` and `detail["duration_seconds"]` are
**pre-existing fields**, unchanged by this milestone in meaning or value —
they already excluded the final `save_run` call before ID-7P0 existed (the
`duration = max(0.0, self._clock() - t0)` line in
`src/athena/scheduling/dry_run.py` predates this milestone). Their only
production/code consumer found by a repo-wide audit is a read-only CLI
diagnostic print (`src/athena/cli.py:458`, `print(f"duration_s :
{result.duration_seconds:.3f}")`) — display-only, with no semantic
dependency on the exact boundary. ID-7P0 does not rename, redefine, or
otherwise touch this field; it only adds new, separately-named diagnostic
phases that are explicit about their own boundary.

Output is additive-only: `detail["timing"]` is a new optional key inside
the existing `runs.detail_json` JSON blob (`SqliteRepository.save_run`,
already a free-form `Mapping[str, object]` serialized with
`json.dumps(..., default=str)`). No schema change, no new table, no
migration, no change to any existing `detail` key's meaning. Enabled only
on the real scheduled path (`src/athena/ops/scheduled_run.py`'s
`DryRunCycleOrchestrator(...)` construction, the one actually driving
PREMARKET/REFRESH/CLOSING under `athena serve --with-cycles` /
`athena run-due`) — the four other `DryRunCycleOrchestrator` construction
sites (`cli.py`, `full_validation.py`, `fast_revalidation.py`,
`symbol_validate.py`) are untouched and remain `enable_timing=False`.

## 3. Existing WorkflowEngine clock impact

**None.** `src/athena/ops/owner_validation.py` and
`src/athena/runtime/workflow.py` were not opened for editing by this
milestone. `_MonoClock`'s deterministic fake-increment semantics are
byte-for-byte unchanged. Per-analytical-phase attribution (indicator/
scoring/decision/EntryQualification internal timing) was deliberately
**not** attempted — extracting that would require plumbing real timing
through `WorkflowStage` execution shared with business-correctness code,
which the owner's own instruction explicitly permits skipping in favor of
whole-scan measurement. `scan_total` (§2) is that whole-scan measurement,
wrapped entirely from *outside* `OwnerValidationPipeline`/`WorkflowEngine`
— zero lines changed inside either.

## 4. Sequentiality audit (source-confirmed, no behavior changed)

- **Daily candle fetch**: sequential, single-instrument-per-call
  (`self._provider.daily_candles(iid, start_day, end_day)` inside
  `for iid in ids:`, `data/ingestion/engine.py:118` pre-existing loop
  structure, timing added around it).
- **Intraday candle fetch**: sequential, single-instrument-per-call, same
  loop pattern (`engine.py:139` area).
- **Quote fetch**: a **true batch call** — `self._provider.quotes(ids)`,
  one call for the whole instrument list.
- **Provider-side concurrency**: **confirmed absent**. A dedicated audit
  of `src/athena/data/providers/kite_provider.py` and
  `kite_transport.py` found no `asyncio`, `ThreadPoolExecutor`, or
  `multiprocessing` anywhere — every transport call is a single blocking
  `urllib.request.urlopen`. `daily_candles`/`intraday_candles` are
  genuinely single-instrument methods on the real Kite provider (not an
  unused batch capability sitting idle) — the sequential per-instrument
  loop in `LiveIngestionEngine` is the *only* structural source of
  per-instrument sequentiality; there is no hidden provider-side batching
  being left on the table for candles. `quotes()` *is* provider-native
  batch (Kite's real `/quote` endpoint accepts multiple `i=` params in one
  HTTP call, chunked at 500 ids per request, `quote_batch_size=500`,
  `config/providers/kite.json:26`), already used as such.

## 5. Provider-limit / rate-limit discovery

Found in `KiteTransport._pace()` (`kite_transport.py:127-139`) and
`config/providers/kite.json:27-33`, matching Zerodha's own documented Kite
Connect limits (also recorded independently in
`src/athena/config/models.py:319-323`'s `KiteRateLimitConfig` docstring
and `docs/adr/ADR-007-owner-triggered-background-validation.md:34-40`,
"verified against current vendor docs"):

| Endpoint class | Enforced minimum interval | Effective rate |
|---|---:|---:|
| `historical` (daily/intraday candles) | 0.334s | ≈3 req/s |
| `quote` | 1.0s | ≈1 req/s |
| `other` | 0.1s | ≈10 req/s |

Enforced via a `threading.Lock` + last-request-timestamp check before
*every* request (`_pace`, called at `kite_transport.py:160`) — this is a
real, always-applied floor, not a best-effort suggestion. On HTTP 429 the
transport retries up to `max_429_retries=3` with exponential backoff
(1s/2s/4s) before failing (`kite_transport.py:157-176`); any other HTTP
error is raised immediately, uncaught/unretried. HTTP timeout is 30.0s
(`kite_transport.py:83`, a Python default, not config-driven).

## 6. A concrete, quantitative partial explanation (available before any measured evidence)

**Corrected (ID-7P0.1) — grounded in verified production configuration and
real persisted evidence, not an assumed instrument count or timeframe
count.** The original version of this section assumed 528 instruments and
one intraday timeframe without checking the real, currently-configured
values — exactly the kind of guess the owner's ID-7P0.1 review correctly
flagged. Both are now verified directly:

- **Timeframes**: `config/ingestion.json` (the file `load_ingestion_config`
  reads for the real Kite-backed scheduled path) sets `"timeframes":
  ["5m", "15m"]` and `"include_daily": true` — **two** intraday timeframes,
  not one, plus the daily candle fetch: **3** sequential historical-class
  calls per instrument per cycle, not 2.
- **Instrument count**: the real scheduled path does not use
  `config/ingestion.json`'s own (empty) `instrument_ids` list — `athena
  serve --with-cycles` → `_execute_run_due` → `HostDueRunner` builds its
  ingest engine via `_build_ingest_engine(..., scope_to_candidates=True)`
  (`src/athena/cli.py:618-622`), which overrides `instrument_ids` to the
  resolved `owner_candidates` set plus a small number of always-included
  index/VIX instruments (`cli.py:130-213`) — **not** the full Kite
  instrument catalog (~10,000+ rows) and **not** exactly 528 either.
- **Real, measured instrument count**: read directly from the live
  `db/athena.db` (read-only, `mode=ro`), five real 2026-09-03 REFRESH
  cycles all show `quotes_fetched=536` (four of them) or `525` (one, a
  cycle with fewer resolved candidates that particular run) with
  `datasets_skipped_empty=0` and `datasets_validated=1609` (or `1576`) —
  i.e. `(1609 - 1 quotes) / 3 timeframes = 536` instruments exactly, and
  `(1576 - 1) / 3 = 525` exactly, for the two observed counts. **536** is
  used below as the representative figure (the more common of the two
  observed counts across the cycles checked).

Both the daily and both intraday candle loops are classified under the
`historical` endpoint class (`kite_transport.py`'s `endpoint_class()`), so
every one of these calls is subject to the enforced 0.334s minimum
interval alone — independent of actual network/processing time per call:

```
536 instruments × 3 historical calls/instrument = 1,608 calls
1,608 calls × 0.334 s/call ≈ 537.1 seconds ≈ 8.95 minutes

quotes: 536 ids, quote_batch_size=500 -> 2 batch requests
2 requests × 1.0 s/request (quote_min_interval_seconds) ≈ 2.0 seconds

total pacing floor ≈ 539.1 seconds ≈ 8.98 minutes
```

This is a **rate-limiter-enforced floor**, not a measurement — it exists
purely because `_pace()` will not let two `historical`-class requests fire
closer together than 0.334s, regardless of how fast the network or the
provider itself responds. Against the ID-6E-observed ~9.38-minute (562.97s)
average cycle duration, this floor alone accounts for **≈95.8%** of the
total (539.1s / 562.97s) — *before* adding any real network round-trip
time, JSON parsing, or validation/normalization work per call, and using
only the pacing minimum, not the actual observed per-call latency. This
substantially raises confidence, even ahead of any natural-cycle
measurement, that ingestion (specifically the historical-candle-fetch
pacing itself, not necessarily network slowness on top of it) is the
dominant latency driver — consistent with, and now much more precisely
explaining, ID-7 discovery's circumstantial EQ-write-clustering finding.
**This remains strong prior evidence, not a measured latency
classification** (§8) — the real per-cycle `ingestion_total` vs.
`scan_total` split the new instrumentation will produce on the next
natural cycle is still required before `INGESTION_DOMINANT` may be
declared as a finding rather than a prior.

## 7. Business-output equivalence (tested, not merely asserted)

`tests/runtime/test_dry_run_schedule.py::TestCycleTimingIntegration::
test_timing_enabled_does_not_change_business_output` runs the same
synthetic ingestion/pipeline result through the orchestrator with
`enable_timing=False` and `enable_timing=True` and asserts identical
`RunStatus`, `candles_written`, `quotes_written`, and pipeline output.
`test_timing_disabled_by_default_no_timing_key_in_detail` confirms the
default (untouched) path never adds a `"timing"` key. Both pass.

## 8. Latency classification (deferred — no natural evidence yet)

`INSUFFICIENT_EVIDENCE`. §6's rate-limiter-floor calculation is a strong,
source-grounded prior favoring `INGESTION_DOMINANT` → `MIXED_INGESTION`
(daily + intraday candle fetch, both pacing-bound), but this document
does not assert that classification as measured fact — no cycle has yet
run with the new `ingestion_total`/`scan_total`/`call_groups`
instrumentation active. That classification will be made in a follow-up
report once natural REGULAR-cycle evidence exists.

## 9. Owner Question 1 (reduction vs. compensation) — preliminary read, not decided here

§6's floor is a structural, provider-imposed constraint (`historical`
class pacing), not an application-level inefficiency ATHENA's own code
chose. This shifts the framing of Owner Question 1 (from the ID-7
discovery document) somewhat: "latency reduction" here would mean
reducing the *number* of sequential historical-class calls per cycle
(e.g., fetching a wider date range per call rather than one call per
instrument per timeframe — Kite's historical endpoint is itself
single-instrument, so this would require either accepting fewer/larger
lookback windows or a fundamentally different per-instrument batching
approach) rather than "removing an inefficiency." This is recorded as
context for the eventual Question 1 decision — **no reduction is
implemented, proposed in detail, or decided in this milestone.**

## 10. Owner Question 2 (evaluation mode) — no new evidence yet

Not reassessed with measured data in this document — deferred to the
follow-up report once natural cycle evidence exists, per instruction.

## 11. Remaining uncertainty

- No natural REGULAR cycle has exercised the new instrumentation.
- §6's rate-limiter floor explains a large share (≈95.8%) of the observed
  average but not all of it — the remainder (real network RTT, JSON
  parsing, validation, normalization, DB writes) is unmeasured until a
  real cycle runs with `ingestion_total`/`call_groups` populated. Given
  how large this share already is, the analytical scan (`scan_total`) is
  expected to be a small fraction of the cycle — but this remains a prior
  expectation, not yet a measurement.
- Analytical-scan sub-phase attribution (indicator/scoring/decision/EQ)
  remains unavailable by design (§3) — only whole-scan `scan_total` will
  be measured.
- The `orchestration_overhead_pre_final_persist` residual (§2)
  deliberately excludes the final `RunRecord` persistence call — its true
  magnitude is expected to be small relative to ingestion, but it is not
  the full "everything after ingestion+scan" quantity a reader might
  assume from its earlier name.
- The production process must be restarted to load this code (§12) —
  this document does not do that.

## 12. Deployment note (not performed by this milestone)

The instrumentation is inert until the live `athena serve --with-cycles`
process is restarted to load it — a real operational action on a running
service, deliberately **not taken by this milestone**. Restarting is a
prerequisite for any natural-cycle evidence to accumulate; it requires
explicit owner go-ahead before being performed.

## 13. Production/provider impact of this milestone itself

None. No provider call was made by this milestone. §6's instrument/
timeframe counts were confirmed via a **read-only** query
(`mode=ro`+`PRAGMA query_only=ON`) of the real, already-persisted
`db/athena.db` — reading existing rows, not writing any. No production
database was written to. No workflow cycle was triggered.

## 14. Correction record (ID-7P0.1, 2026-09-03)

Owner/Chief Architect review of the original ID-7P0 instrumentation found
one narrow measurement-contract inaccuracy, corrected here without
touching business behavior:

1. **Boundary mislabeling.** The original `finalization` phase was
   documented as accounting for "everything else in the method (RunRecord
   construction, `save_run` calls)" — plural, implying both the initial
   RUNNING write and the final COMPLETED/FAILED write. In fact `duration`
   (and everything derived from it) is captured strictly *before* the
   final `save_run` call, so the residual only ever covered the first
   write. Corrected by renaming the phase to
   `orchestration_overhead_pre_final_persist` and stating its exact,
   bounded scope explicitly (§2).
2. **No fix by adding a write.** Per explicit instruction, this was not
   "fixed" by adding a second write, reordering the existing write, or
   otherwise changing `RunRecord`/`save_run` behavior purely to make the
   residual complete — that would make the observer change the very
   operation being measured. `duration_seconds` (pre-existing,
   §2.1) is unchanged; only the new diagnostic's own naming/documentation
   was corrected.
3. **Unverified call-count assumption.** The original §6 assumed 528
   instruments and a single intraday timeframe without checking the real
   production `config/ingestion.json` (which configures **two** intraday
   timeframes, `5m` and `15m`) or the real scheduled-path instrument
   scoping (`cli.py`'s `scope_to_candidates=True`, not the static config's
   own empty `instrument_ids`). Corrected using the real, verified
   configuration plus a direct read-only query of actual persisted
   2026-09-03 cycle data (536 instruments, 1,608 historical calls per
   cycle, confirmed exactly against `datasets_validated`/`quotes_fetched`
   with `datasets_skipped_empty=0`) — revising the pacing-floor estimate
   from ≈352.7s/≈63% to ≈539.1s/≈95.8% of the ID-6E-observed average.

Tests added: 3 new focused tests in
`tests/runtime/test_dry_run_schedule.py` proving (a) with a deterministic
injected clock, `ingestion_total + scan_total +
orchestration_overhead_pre_final_persist` equals the measured
pre-final-persist `duration_seconds` exactly; (b) `save_run` is called
exactly twice (RUNNING, then terminal status) whether timing is enabled
or not — no extra write was introduced; (c) the final `save_run` call
happening after `detail["timing"]` is fully constructed means nothing
inside that final call can retroactively change any previously-recorded
timing figure. Full repository suite: 3,259 passed (was 3,256), 0
skipped. Ruff clean on all touched files. `git diff --check` clean.

No production source outside `src/athena/scheduling/dry_run.py` (the
docstring/comment correction) required changing for this correction — the
instrumentation architecture itself (§2's remaining, unchanged claims)
was already accepted.
