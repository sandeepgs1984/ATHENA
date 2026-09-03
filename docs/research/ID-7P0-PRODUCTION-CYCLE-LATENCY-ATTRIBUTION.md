# ID-7P0 — Production Cycle Latency Attribution

**Status:** `ID-7P0 INSTRUMENTATION READY — EVIDENCE ACCUMULATION PENDING`.
Instrumentation implemented, tested, and Ruff-clean; wired into the real
scheduled-cycle code path (`src/athena/ops/scheduled_run.py`). **Not yet
active in the running production process** — the live `athena serve
--with-cycles` server holds the old code in memory and must be restarted
to load it. No natural REGULAR-cycle evidence exists yet.

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
  528-instrument analytical scan) call in a `scan_total` phase. A
  `finalization` phase is derived as `total_cycle_duration -
  ingestion_total - scan_total` — safe because the two wrapped phases are
  sequential and non-overlapping within the same `try` block, so this
  arithmetic double-counts nothing and is exhaustive of everything else in
  the method (RunRecord construction, `save_run` calls).

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

Universe size is 528 instruments (confirmed via `owner_candidates` in the
ID-6E/ID-7 discovery work). Both the daily and intraday candle loops are
classified under the `historical` endpoint class, so **every one of the
528 × 2 = 1,056 sequential candle-fetch calls in a normal cycle is subject
to the enforced 0.334s minimum interval alone** — independent of actual
network/processing time per call:

```
1,056 calls × 0.334 s/call ≈ 352.7 seconds ≈ 5.88 minutes
```

This is a **rate-limiter-enforced floor**, not a measurement — it exists
purely because `_pace()` will not let two `historical`-class requests fire
closer together than 0.334s, regardless of how fast the network or the
provider itself responds. Against the ID-6E-observed ~9.38-minute average
cycle duration, this floor alone accounts for **≈63%** of the total —
*before* adding any real network round-trip time, JSON parsing, or
validation/normalization work per call. This substantially raises
confidence, even ahead of any natural-cycle measurement, that ingestion
(specifically the historical-candle-fetch pacing, not necessarily network
slowness) is the dominant latency driver — consistent with, and now
partially explaining, ID-7 discovery's circumstantial EQ-write-clustering
finding. **This is not yet a final classification** (§8) — it is strong
prior evidence pending the real per-cycle `ingestion_total` vs.
`scan_total` split the new instrumentation will produce on the next
natural cycle.

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
- §6's rate-limiter floor explains a large share (≈63%) of the observed
  average but not all of it — the remainder (real network RTT, JSON
  parsing, validation, normalization, DB writes) is unmeasured until a
  real cycle runs with `ingestion_total`/`call_groups` populated.
- Analytical-scan sub-phase attribution (indicator/scoring/decision/EQ)
  remains unavailable by design (§3) — only whole-scan `scan_total` will
  be measured.
- The production process must be restarted to load this code (§12) —
  this document does not do that.

## 12. Deployment note (not performed by this milestone)

The instrumentation is inert until the live `athena serve --with-cycles`
process is restarted to load it — a real operational action on a running
service, deliberately **not taken by this milestone**. Restarting is a
prerequisite for any natural-cycle evidence to accumulate; it requires
explicit owner go-ahead before being performed.

## 13. Production/provider impact of this milestone itself

None. No provider call was made by this milestone (all findings in §4-6
came from static source/config inspection, not a live request). No
production database was written to. No workflow cycle was triggered.
