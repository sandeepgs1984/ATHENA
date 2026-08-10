# ADR-009 — Split read/write SQLite connections for true WAL concurrency

| | |
|---|---|
| Status | Accepted |
| Date | 2026-08-10 |
| Deciders | sandeep (owner) |

## Context

`SqliteRepository` (`src/athena/data/store/repository.py`) opens exactly one
`sqlite3.Connection` at startup and serializes every call — reads and writes
alike — through one `threading.RLock()`. The class's own docstring states why:

> The connection is created with `check_same_thread=False` so FastAPI (and
> other multi-threaded callers) may share one repository instance. All access
> is serialized through an `RLock` because a sqlite3 connection is not
> otherwise thread-safe.

That reasoning is correct: a single Python `sqlite3.Connection` object cannot
safely be called concurrently from multiple threads without external
serialization. But the fix applied — one connection, one lock, covering
every read and every write, for the entire process — discards the
concurrency the database's own `journal_mode=WAL` (`repository.py:73`) exists
to provide. WAL normally allows readers and writers to proceed concurrently,
and normally allows multiple readers to proceed concurrently with each
other; writer serialization and SQLite busy/locking edge cases can still
occur and are not eliminated by WAL mode itself. Today ATHENA serializes
*everything* against *everything*, in a single-threaded queue, regardless of
what SQLite itself could normally run in parallel.

This is not a theoretical concern. Across one live debugging session
(2026-08-10), every distinct slowdown traced back to this same queueing,
after five unrelated, individually-real bugs were found and fixed first:

- A scheduled REFRESH cycle (full 517-symbol universe, ~540-650s duration —
  itself an inherent Kite rate-limit floor, not a bug) held the shared
  connection busy enough that a concurrent single-symbol "Revalidate" click,
  whose own work measured ~2.2s in isolation, experienced 30+ seconds of
  wall-clock delay.
- The Decisions & Trace board's cold load walked up to 50 pages
  (`/api/v1/decisions`) — reconstructing "one decision per instrument" from
  the full historical event log (91,241+ rows for 377 tracked instruments,
  since decisions are immutable/append-only and re-evaluated every cycle) —
  costing 25-30s+, fixed by adding `GET /decisions/latest` (190ms).
- Even after that fix and a background-poll fix, a single-symbol validate
  for `ABLBL` still took ~42s end to end. Traced precisely: the backend
  `POST /validate` itself completed in 8s; the remaining ~34s was spent
  inside `loadMarketIntelligence()` (bundles market summary, the validation
  funnel, 100 rows of pipeline history, index leadership, and top
  opportunities into one call) queueing behind a separately-timed
  Operations-tab poller hitting overlapping endpoints on its own cadence.
- Confirming evidence: after a cold restart, "Portfolio Overview" (total
  value, cash available) — a trivial query with no Kite calls, no catalog
  resolution, nothing expensive in its own logic — was also slow to
  populate. A cold page load fires 15-20+ requests across Overview, Market,
  and Operations tabs within a couple of seconds; every one of them, cheap
  or expensive, takes its turn through the same single connection and lock.

The five bugs fixed this session (FAST-tier cadence, the decisions page
walk, a `market_snapshots.ts` uniqueness bug, an unconditional per-tick Kite
catalog fetch, and the decisions-cache cold-load path) were each real and
each reduced load measurably. None of them address the structural cause:
concurrent reads block each other and block behind writes for no reason
SQLite itself requires.

Every one of `SqliteRepository`'s ~50 public methods routes through exactly
four internal primitives: `_write`, `_write_many`, `_query_one`, `_query_all`
(`repository.py:942-989`). Of the call sites into those four, 33 are reads
and 16 are writes — the overwhelming majority of traffic, and 100% of the
incidents traced this session, are reads.

## Decision

**Option C — split read connections from the write connection.** The
objective is narrowly scoped: remove unnecessary read-vs-read and
read-vs-write serialization, while preserving ATHENA's proven write
correctness and the existing `SqliteRepository` API contract exactly as is.
This is not a general "make SQLite faster" effort.

Keep exactly one write connection, guarded by exactly the `RLock` that
exists today, with exactly the same transactions, schema initialization,
backups, and integrity checks — none of that changes. Give each serving
thread its own dedicated **read-only** connection to the same WAL-mode
database file (`sqlite3.connect(f"file:{path}?mode=ro", uri=True)` —
physically incapable of executing a write statement, even by accident).
Route `_query_one` and `_query_all` through the calling thread's read
connection instead of the shared write connection/lock. `_write` and
`_write_many` are untouched.

`journal_mode=WAL` is a property of the database file, set once and
persisted in the file header — not a per-connection setting — so every new
read connection picks up WAL semantics automatically, with no additional
setup.

**Read-connection lifecycle (explicit):**

- **Created lazily**, on first use by a given thread, and only after
  `SqliteRepository.initialize()` has already run schema setup/migration on
  the write connection — a read connection is never opened at repository
  construction time, only on first `_query_one`/`_query_all` call from that
  thread.
- **Owned by the calling thread**: stored in a `threading.local()`, one
  connection per thread, never shared or handed across threads.
- **Reused by that thread** for every subsequent read for the lifetime of
  the thread — not reopened per call.
- **Never used for writes**: opened with the `mode=ro` URI flag, which
  makes a write attempt through it fail at the SQLite level rather than
  merely being a naming convention or an application-level rule.
- **Closed through a defined per-thread cleanup hook, not a central
  registry.** `SqliteRepository` exposes an explicit method the *calling
  thread itself* invokes to close and discard its own read connection
  (e.g. as part of `close()` when called from that thread, or from
  framework-level per-request/per-task teardown where the owning
  lifecycle — FastAPI's request scope, a CycleWorker task — exposes a
  reliable "this thread/task is done" hook). Repository/runtime shutdown
  additionally closes the *shutdown-calling thread's own* read connection
  (if it has one) and the shared write connection, through the existing
  shutdown path — unchanged from today.
  This deliberately does **not** attempt to close read connections
  belonging to *other*, independently terminating worker/request threads:
  doing so reliably would require a central registry of live per-thread
  connections that the shutdown thread could reach into and close on
  another thread's behalf — exactly the connection-pool/connection-manager
  shape Option C is scoped to avoid. Python does not guarantee a
  `threading.local` destructor runs when a thread exits, so for a thread
  that terminates without ever calling the per-thread cleanup hook, its
  read connection is reclaimed by normal Python/OS process teardown when
  the connection object and its owning thread are garbage collected, not
  by any explicit application-level close call. This is a stated,
  accepted limitation of the deliberately small Option C design, not a
  bug to be engineered around — see the test plan below for exactly what
  is and isn't proven as a result.

**No public `SqliteRepository` method signature changes.** This is entirely
an internal routing change inside two private methods (`_query_one`,
`_query_all`). Every one of the ~50 public methods, and every one of their
callers across the codebase, keeps its exact current signature and
behavior.

## Alternatives considered

- **Option A — full connection-per-thread pool, remove the write lock
  entirely,** serialize writers via SQLite's own `busy_timeout` retry
  instead of a Python lock. This is the textbook end state for a WAL-mode
  SQLite app, but it is a materially larger and riskier change: it touches
  the write path's correctness story (today's explicit, well-understood
  lock-based serialization) as well as the read path, for no additional
  benefit over Option C — nothing traced this session was writer-vs-writer
  contention. Worth reconsidering later *only* if write contention itself
  becomes a measured bottleneck, which nothing in this investigation showed.
- **Option B — priority queue on top of the existing single connection** —
  let interactive requests jump ahead of background/scheduled work waiting
  on the same lock. Rejected: Python's standard library has no
  priority-aware lock, so this means building and maintaining a custom one,
  and it only treats the queueing symptom — reads still couldn't run in
  parallel with each other, which is the actual waste WAL already solves.
  A workaround, not a fix.
- **Option D — do nothing, keep patching individual slow call sites as
  they surface.** Rejected per this session's own evidence: five real,
  distinct bugs were found and fixed, and a sixth, unrelated symptom
  (Portfolio Overview) surfaced immediately after, confirming the pattern
  is structural rather than a finite list of bad queries.

## Consequences

- Interactive dashboard reads (portfolio, decisions, market summary,
  pipelines) stop queueing behind unrelated background reads and writes —
  directly targets every incident traced this session.
- Write path (ingestion, decision persistence, run records, snapshots) is
  completely unchanged: same connection, same lock, same transaction
  semantics, same crash-safety guarantees.
- New failure mode to guard against in testing: a read connection opened
  before a schema migration runs on the write connection could see a stale
  schema until it reconnects — mitigated by opening read connections lazily
  per-thread (after startup's `initialize()` has already run) rather than
  eagerly at process start.
- Does not address writer-vs-writer serialization or reduce the number of
  requests the dashboard fires per page load/tab-switch — those remain
  future, separately-scoped concerns (Option A; and the per-page
  request-volume question raised by the `loadMarketIntelligence()` /
  Operations-tab overlap, which is a frontend concern independent of this
  ADR).
- If a future data vendor or workload introduces genuine write-heavy
  contention, Option A should be revisited with real measurements at
  that time.

## Concurrency test plan (required before implementation)

To be run against the implementation, not the current code, as the
acceptance gate. Item 3 deliberately does not test anything new: Option C
does not change the write model, so its job is to prove the *existing*
shared write connection + `RLock` still serializes writes exactly as it
does today — not to add or exercise any retry/backoff behavior, speculative
or otherwise, that doesn't already exist in the codebase.

1. **Concurrent reads do not wait on the Python write lock while a slow
   write transaction is in progress.** Start a write inside a transaction
   that sleeps for N seconds before committing (simulating a large
   `add_candles`/ingestion write); concurrently issue reads through several
   threads. Assert every read completes in native time, not N seconds —
   proving the read connections are unaffected by an in-flight write.
2. **Concurrent reads do not serialize behind one another.** Fire M
   concurrent reads (mix of cheap point lookups and heavier aggregate
   queries, e.g. `list_latest_decisions_by_instrument`) from M threads;
   assert wall-clock for the batch is close to the single slowest query,
   not the sum — proving true parallelism, not serialization with a
   shorter queue.
3. **Existing write serialization remains correct.** Fire concurrent
   writes from multiple threads against the unchanged shared write
   connection + `RLock`, and assert the final row counts/values are
   exactly what a fully serial execution would produce — no lost updates,
   no corruption. This proves Option C left the write model's existing,
   already-proven correctness untouched; it does not introduce or assert
   any new retry/backoff/busy-handling behavior.
4. **Committed writes become visible through read connections without a
   reconnect or checkpoint.** A thread writes a row on the write
   connection, then immediately reads it back on its own thread-local read
   connection; assert it's visible with no explicit reconnect or
   `wal_checkpoint` call required.
5. **Read connections are physically read-only.** Attempt a write through
   the read-connection code path in a test; assert it fails at the SQLite
   level (the `mode=ro` URI itself rejecting the statement), not merely by
   application-level convention.
6. **Thread-local connection lifecycle is safe.** This test does **not**
   assert that a central shutdown thread can reach into and close read
   connections owned by other, independently terminating threads — see the
   stated limitation in Decision. It asserts, per controlled worker thread:
   - the thread creates and uses its own read connection;
   - the thread invokes the defined per-thread cleanup hook before exiting
     (in every case this test controls, since the test itself drives each
     worker thread's lifecycle);
   - that connection is verifiably closed after the hook runs;
   - one thread never receives or reuses another thread's connection;
   - a subsequent read on a thread *after* its own explicit cleanup lazily
     creates a fresh connection, rather than reusing or erroring on the
     closed handle.

   Separately, this test asserts repository/runtime shutdown: closes the
   shutdown-calling thread's own read connection if it has one, and closes
   the shared write connection through the existing shutdown path
   (unchanged behavior, re-verified here) — and does **not** attempt, and
   is not expected, to close read connections belonging to other threads
   that terminated independently without invoking their own cleanup hook.
7. **All existing tests remain green without behavioral changes.** No test
   in the current suite should need a behavioral change — only fixture/setup
   adjustments if a test directly inspects `SqliteRepository`'s internal
   connection count.
8. **ABLBL validate + `loadMarketIntelligence()` concurrency scenario,
   before/after.** Reproduce the real scenario traced this session (a
   single-symbol validate concurrent with the `loadMarketIntelligence()`-
   shaped read load it triggers) against both the current code and the
   Option C implementation, and record actual before/after wall-clock
   timings for the comparison — not just a pass/fail assertion.
9. **Portfolio Overview cold-load scenario, before/after.** Reproduce the
   cold-restart page-load burst that made Portfolio Overview slow to
   populate, against both the current code and the Option C implementation,
   and record before/after timings — this was an independent, real-world
   symptom and must be verified directly, not assumed to be fixed as a
   side effect of item 8.

## Implementation gate

No implementation begins until the owner has approved **both** this ADR and
the concurrency test plan above. This ADR stays `Proposed` until the owner
explicitly marks it `Accepted` — status is not changed unilaterally as part
of drafting or refining it.

Once approved, implementation lands as its own dedicated
performance/concurrency milestone, following the normal process in full:
Design → Implement → Test → Self-Validate → Milestone Review Summary →
Owner/Chief Architect approval. Never auto-continue past that approval gate.

**Scope is exactly the following four primitives — nothing else:**

| Primitive | Change |
|---|---|
| `_write` | Unchanged |
| `_write_many` | Unchanged |
| `_query_one` | Route through the calling thread's lazily-created read-only connection |
| `_query_all` | Route through the calling thread's lazily-created read-only connection |

**Explicitly out of scope for this milestone** — none of the following are
implied or permitted by this ADR, regardless of how small or "obviously
related" they might seem while implementing:

- Any change to a public `SqliteRepository` method's signature or behavior.
- Any broader repository redesign.
- A global read-connection registry (this is precisely what the corrected
  lifecycle/test #6 above deliberately avoids introducing).
- A general-purpose connection pool (this is one lazily-created read
  connection per thread via `threading.local()`, not a managed pool with
  checkout/checkin, sizing, or eviction policy).
- Cross-thread connection management of any kind (one thread reaching into
  or closing another thread's connection).
- Weak-reference connection tracking, or any other mechanism to observe or
  reclaim another thread's connection from outside that thread.
- An async SQLite migration (`aiosqlite` or similar).
- New retry/backoff infrastructure for the write path (the existing
  `RLock`-based serialization is verified as-is per test #3, not replaced
  or augmented).
- Any frontend/dashboard cleanup (the `loadMarketIntelligence()` /
  Operations-tab request-volume observation from this session's evidence is
  noted for future, separately-scoped consideration — not addressed here).
- Any query/index optimization or other unrelated refactoring encountered
  along the way — those go through their own change, not folded into this
  one.

The objective is exactly what's stated in Decision: remove unnecessary read
serialization while preserving ATHENA's proven write correctness and the
existing repository API contract. Nothing more.
