# ADR-007 — Owner-triggered full-universe validation as a background host job

| | |
|---|---|
| Status | Accepted |
| Date | 2026-07-28 |
| Deciders | sandeep (owner) |

## Context

MI-5 of the Market Intelligence redesign wires the mock's "Run Full Validation"
action to the real `OwnerValidationPipeline.run()` engine, and the owner has
asked for a "Validate All" action over the Universe table. Both mean the same
operation: validate every active candidate (507 today) in one go. Nothing in
ATHENA exposes this from the dashboard right now — full-universe validation
exists only as `./athena-daily force-refresh` / `athena cycle --trigger refresh`,
whose own help text warns it "can take a long time".

**Why the existing scoped-validate path cannot simply be called 507 times.**

- `ValidateSymbolsRequest.symbols` (`src/athena/api/v1/dtos/market.py:51`) caps a
  request at 20 symbols, so "all" would be 26 sequential HTTP calls.
- Each call builds a fresh `KiteProvider` and re-downloads the entire
  `/instruments/NSE` catalog CSV (`_ensure_catalog`, cached per instance only) —
  26 multi-megabyte dumps for one logical action.
- Each call persists its **own** run record, so the MI-3 Validation Pipeline
  funnel — which reads a single newest run — would report "Universe 20" instead
  of 507. The funnel would be honest about the run and misleading about the day.
- `validate_symbols()` is invoked synchronously from the request thread
  (`CandidatesService.validate_candidates`). A full-universe run cannot complete
  inside an HTTP request: browser and any reverse proxy time out long before it,
  and the worker thread is held for the duration.

**Provider rate limits (Kite Connect, verified against current vendor docs).**

| End-point | Limit | Full-universe cost today |
|---|---|---|
| Historical candle | 3 req/s | 507 symbols × (1 daily + 1 intraday 5m) = 1,014 requests → **338 s floor** |
| Quote | 1 req/s | 510 ids (507 + 2 indices + VIX) exceed `quote_batch_size: 500` → 2 back-to-back calls, already a breach |
| All other end-points | 10 req/s | 1 instruments-catalog fetch per run |

There are no per-minute or per-day caps on market data (only on order placement,
which ATHENA never performs). So volume is not the constraint — **pacing** is,
and ATHENA has none: `LiveIngestionEngine.run_cycle` iterates instruments in a
tight serial loop with no inter-request delay
(`src/athena/data/ingestion/engine.py`), and `UrllibKiteTransport._request`
converts any `HTTPError` — including 429 — into a hard `ProviderError`
(`src/athena/data/providers/kite_transport.py`), which fails the entire run and
discards every symbol already fetched. This gap is **pre-existing** and already
applies to `./athena-daily force-refresh`; a dashboard button would merely make
it easy to trigger.

**Existing precedent for background work in the host.** `athena serve
--with-cycles` already runs long pipeline work inside the API process:
`CycleWorker` (`src/athena/ops/serve_runtime.py`) is a daemon thread polling a
tick function, guarded by `CycleRunnerLock` — an `fcntl` advisory lock at
`artifacts/locks/cycle-runner.lock` that deliberately prevents the serve worker
and the launchd `run-due` scheduler from overlapping. Transient status is kept in
`ServeRuntime` (process-local, mutex-guarded) and surfaced read-only through the
health provider. Background execution in the host is therefore an established
pattern, not a new one; what is new is an **owner-triggered** (rather than
schedule-triggered) long job, and a way for the dashboard to watch it.

Constraints: architecture is frozen (§19 — no new execution model without an
ADR); determinism, replayability and explainability must be preserved;
minimal dependencies; every failure must fail loudly; no order-placement code.
`config/base.json`'s `performance_budgets_seconds` (`refresh: 10`,
`dashboard: 5`) describe interactive latency and were never intended to cover a
multi-minute full-universe job.

## Decision

Expose full-universe validation as an **owner-triggered background job in the
serve process, reusing the existing `CycleWorker`/`CycleRunnerLock`
machinery** — not as a synchronous endpoint, not as browser-side chunking, and
not via a new job queue or scheduler dependency.

1. **One run, one run_id.** The job invokes the existing full-universe path
   (`OwnerValidationPipeline` over all active candidates via
   `DryRunCycleOrchestrator`), producing exactly one `RunRecord` — so the MI-3
   funnel, the Universe table and Inspect Trace all describe the same real run.
   No new engine, no new pipeline, no duplicated orchestration.
2. **Single-flight, enforced by the existing lock.** The trigger endpoint
   acquires `CycleRunnerLock`; if launchd `run-due` or a `--with-cycles` worker
   holds it, the request is rejected with `409 Conflict` and an explanatory
   detail. Two concurrent writers hammering Kite and SQLite is not an
   acceptable outcome.
3. **Progress is transient; the outcome is durable.** Live progress
   (state, symbols completed/total, started_at, current stage, last error) lives
   in `ServeRuntime` alongside `last_cycle` — process-local, non-persistent, read
   through a new read-only status endpoint the dashboard polls. The durable,
   replayable record stays exactly where it already is: the `runs` table. **No
   new schema, no new persisted job table, no SCHEMA_VERSION bump.**
4. **Pacing and 429 handling move into the provider layer** (bundled into the
   same milestone, per owner decision): a configurable minimum interval per
   end-point class (historical 3 req/s, quote 1 req/s, other 10 req/s, values in
   `config/providers/kite.json`, no magic numbers) plus a bounded retry with
   backoff on HTTP 429 only. Retries are exhaustible — once exhausted the run
   still fails loudly with the provider's message. Pacing affects wall-clock
   only, never which candles/quotes are returned, so determinism and
   replayability are untouched.
5. **The frozen scoped-validate contract is unchanged.** `POST
   /api/v1/market/validate` keeps its 20-symbol cap and its synchronous
   semantics. Full-universe validation is a *different* action with no symbol
   list ("all active candidates"), so no existing caller changes behaviour.
6. **This action is explicitly outside `performance_budgets_seconds`.** It is a
   deliberate multi-minute operation; the budgets continue to govern
   interactive reads. Documented, not silently exceeded.

## Alternatives considered

- **Synchronous endpoint that validates all 507 inline.** Rejected: 6–15 minutes
  inside one HTTP request, guaranteed browser/proxy timeout, one serve worker
  thread held hostage, and a client disconnect leaves the owner with no way to
  observe an operation that is still running and still writing.
- **Browser-side chunking (26 sequential calls of 20).** Rejected as a
  correctness regression despite needing no backend work: 26 run records for one
  logical action, a funnel that reports 20 of 507, 26 full instrument-catalog
  downloads, progress that dies if the tab closes, and no 429 protection.
- **A generic async job framework (Celery/RQ/APScheduler or an in-house queue).**
  Rejected: violates minimal-dependencies for a single-user localhost
  workstation, and duplicates `CycleWorker`, which already does exactly this job
  under an advisory lock.
- **Persist job progress in a new `jobs` table.** Rejected: progress is
  transient operational state, not evidence. The durable outcome is already the
  run record; a second persisted representation of the same thing would be one
  more thing to keep consistent for zero analytical value.
- **Raise `ValidateSymbolsRequest.max_length` from 20 to 600.** Rejected: it
  changes a frozen request contract to paper over the real problem (request
  lifetime and pacing) and still fails on timeout.
- **Leave full-universe validation on the CLI only.** Rejected by the owner for
  MI-5, but retained as the unattended path: launchd `run-due` remains the
  scheduler of record, and this ADR deliberately reuses its lock rather than
  competing with it.

## Consequences

- Easier: the owner can trigger a real, single-run, full-universe validation
  from the dashboard and watch it progress; the funnel and Universe table finally
  describe the whole universe rather than the last-clicked symbol.
- Easier: the pre-existing 429 exposure in `./athena-daily force-refresh` is
  fixed at the provider layer, benefiting every existing caller, not just the
  new button.
- Harder / accepted: the serve process becomes the execution host for a
  multi-minute owner-triggered job. A host restart mid-job orphans it — the run
  must therefore be left visibly incomplete/FAILED and the transient progress
  state must reset on boot, never linger as a permanently "in progress" lie.
- Accepted debt: `ServeRuntime` is process-local, so progress is invisible to any
  second process and would be wrong under `uvicorn --workers > 1`. ATHENA runs a
  single localhost worker by design; **this ADR must be revisited before any
  multi-worker or multi-host deployment.**
- Determinism, replayability and explainability are unaffected: same engines,
  same config snapshot, same persisted run/decision/trace records. Pacing and
  429 retries change timing only.
- Revisit if a second market-data vendor (DD-1 successor) is adopted, since the
  per-end-point pacing values are vendor-specific configuration.

## Implementation gate

MI-5 implementation must not begin until **both** MI-4 is approved and this ADR
is accepted. **Gate cleared 2026-07-28** (MI-4 approved, ADR accepted). MI-5
splits so that provider pacing + 429 retry (testable in isolation, no UI) lands
before the background job and its UI.
