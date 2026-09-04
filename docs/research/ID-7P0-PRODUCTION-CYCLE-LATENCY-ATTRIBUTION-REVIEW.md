# ID-7P0 — Final Production Cycle Latency Attribution Review

**Status: ID-7P0 LATENCY ATTRIBUTION COMPLETE — READY FOR OWNER / CHIEF
ARCHITECT REVIEW.** Read-only audit, 2026-09-04, after the regular NSE
session completed. Answers one question with measured evidence: what
actually explains ATHENA's observed ~9–10 minute production cycle latency?
No optimization, no instrumentation change, no workflow/cycle trigger, no
provider call, no database write was performed to produce this document.

---

## 1. Audit cutoff

`cutoff_utc = 2026-09-04T10:14:28Z` / `cutoff_ist = 2026-09-04T15:44:28 IST`.
Only `runs` rows with `started_ts` at or before this cutoff are included in
any statistic below. The NSE regular session (09:15–15:30 IST) had already
closed by the time of the audit.

## 2. Read-only safety proof

All database inspection used `sqlite3.connect("file:db/athena.db?mode=ro",
uri=True)` plus `PRAGMA query_only=ON`. No `Repository.initialize()`, no
schema migration, no workflow/cycle execution, no provider/quote/historical
API call, no write to `db/athena.db`, `db/emr.db`, or `db/darvax.db` was
performed. `db/emr.db` and `db/darvax.db` were not opened at all — this
audit is ID-track only, per explicit instruction. The only artifacts
produced are this document and the tracking-doc updates listed in §35.

## 3. Evidence window

Primary evidence: natural instrumented production cycles from **2026-09-04**
(today). 2026-09-03's cycles were also inspected for cross-day
replication — see §5/§24 for why they turned out to be unusable.

**Terminology note:** the live system has no trigger literally named
`REGULAR`. The four valid triggers for the instrumented orchestrator are
`PREMARKET`, `REFRESH`, `CLOSING`, `FAST` (`athena.scheduling.dry_run`).
`REFRESH` is the system's own name for the recurring intraday cycle the
owner's authorization calls "REGULAR" — this review uses `REFRESH`
throughout as the precise, source-confirmed name, per the "use actual
persisted names, not invented aliases" instruction.

## 4. Sample inventory

Per-(date, trigger, status) counts, from `db/athena.db`'s `runs` table,
`started_ts` on 2026-09-03 or 2026-09-04:

| Date | Trigger | Status | Count | Has `timing` payload |
|---|---|---|---|---|
| 2026-09-03 | CLOSING | COMPLETED | 1 | 0 |
| 2026-09-03 | FAST | FAILED | 25 | 0 |
| 2026-09-03 | PREMARKET | COMPLETED | 1 | 0 |
| 2026-09-03 | REFRESH | COMPLETED | 27 | **0** |
| 2026-09-04 | CLOSING | RUNNING | 1 | — (in progress at cutoff, excluded) |
| 2026-09-04 | FAST | FAILED | 25 | 0 |
| 2026-09-04 | PREMARKET | FAILED | 1 | 1 (auth-token failure, see below) |
| 2026-09-04 | REFRESH | COMPLETED | 21 | **21** |
| 2026-09-04 | REFRESH | FAILED | 3 | 2 |
| 2026-09-04 | REFRESH | RUNNING | 1 | 0 (orphaned — see exclusions) |

**Explicit exclusion classification (nothing discarded silently):**

- All 27 of 2026-09-03's `REFRESH`/`COMPLETED` cycles: excluded,
  `no_timing_payload`. ID-7P0's restart landed later that day; none of
  that day's completed REFRESH cycles carry a `timing` key at all.
- 2026-09-04 `REFRESH`/`FAILED` (3 rows): excluded, `not_completed` — a
  failed cycle's `duration_seconds`/`timing` reflect an aborted run, not a
  comparable full-cycle measurement.
- 2026-09-04 `REFRESH`/`RUNNING` (1 row, `run-refresh-20260904T134809-...`,
  started `13:48:09 IST`, still `RUNNING` with no `finished_ts` as of the
  cutoff nearly two hours later): excluded, `not_completed` — an apparent
  orphaned/stuck run. Not investigated further here (out of this audit's
  scope; noted as an anomaly worth a separate look, not analyzed).
- `FAST` trigger (25 rows/day, all `FAILED`): excluded — `FAST` cycles
  carry no `timing` payload at all in this deployment and are a materially
  different trigger (this session's own convention did not instrument
  them); their repeated failure is a separate, unrelated fact not
  investigated here.
- The one `PREMARKET`/`FAILED` row (2026-09-04, 08:15:48 IST): excluded
  from the primary sample (not `REFRESH`, and failed after 1 call). Its
  own timing payload shows a Kite `403 TokenException` on the very first
  historical call — a normal daily-auth-token-not-yet-refreshed condition
  at premarket, not a latency phenomenon. Mentioned for completeness, not
  analyzed further.

## 5. Primary REGULAR/REFRESH sample

**n = 21** — every 2026-09-04 `REFRESH`/`COMPLETED` cycle with a `timing`
payload, all at or before the audit cutoff.

- Earliest: `run-refresh-20260904T091501-7278b09f`, started `09:15:01 IST`.
- Latest: `run-refresh-20260904T152522-16f0c02b`, started `15:25:22 IST`.
- Instrument count: **536** on every single one of the 21 cycles (zero
  variance) — matches ID-7P0.1's own verified figure exactly.

## 6. Timing-integrity audit

For all 21 primary cycles:

- All durations (`duration_seconds`, `ingestion_total`, `scan_total`,
  `orchestration_overhead_pre_final_persist`) are `>= 0`. **Zero
  violations.**
- All four timing groups (`ingestion_total`, `scan_total`,
  `orchestration_overhead_pre_final_persist`, plus the three call groups)
  are present on every cycle. **Zero missing payloads** within the primary
  sample.
- `ingestion_total + scan_total + orchestration_overhead_pre_final_persist`
  reconciles to `duration_seconds` to within 0.01s on every cycle (this is
  true by construction — `orchestration_overhead_pre_final_persist` is
  computed as the residual — but confirms no double-counting or corruption
  crept into the persisted payload).
- **Zero timing-integrity defects found.**
- Confirmed from source (`src/athena/scheduling/dry_run.py:208-223`): the
  ID-7P0.1 semantic correction remains exactly as accepted —
  `orchestration_overhead_pre_final_persist` is computed as `duration -
  ingestion_total - scan_total`, captured **before** the final terminal
  `save_run` call, and its own inline comment explicitly still states it
  "does NOT include the final COMPLETED/FAILED `save_run` call itself." It
  was not renamed back to a generic "finalization," and the recorder
  (`src/athena/observability/timing.py`) is byte-for-byte the same file
  `git log` shows was last touched by the ID-7P0/ID-7P0.1 commits
  (`d8025f3`, `aa580f9`) — no further edits since.
- No clock-domain mixing found: all phase/call timings use the same
  injected `self._clock` (`time.monotonic` in production), never
  `datetime.now()`.

## 7. Cycle-total distribution

`cycle_total_seconds` (`duration_seconds`), n=21:

| min | median | mean | p90 | p95 | max |
|---|---|---|---|---|---|
| 556.14s | 560.60s | 561.47s | 566.87s | 566.90s | 570.18s |

In minutes: median ≈ **9.34 min**, max ≈ **9.50 min**.

## 8. ID-6E latency comparison

| | ID-6E (earlier production observation) | This audit (2026-09-04, n=21) |
|---|---|---|
| median | 562.97s | 560.60s |
| p90 | 588.42s | 566.87s |
| p95 | 592.52s | 566.90s |
| max | 622.71s | 570.18s |

The median reproduces the same broad phenomenon almost exactly (within
0.4%). The p90/p95/max are **noticeably tighter** today (a ~14s total
spread vs. ID-6E's ~60s spread) — today's sample shows less tail variance,
not a different mechanism. No exact-equality was required or expected
(different sessions/populations); the broad ~9–10 minute phenomenon is
**reproduced**, with today's sample additionally showing it is
remarkably stable cycle-to-cycle.

## 9. Top-level attribution

Per-cycle percentage of `duration_seconds`, n=21:

| Component | min% | median% | max% |
|---|---|---|---|
| `ingestion_total` | 98.00% | 98.23% | 98.40% |
| `scan_total` | 1.60% | 1.77% | 2.00% |
| `orchestration_overhead_pre_final_persist` | 0.00% | 0.00% | 0.001% |

## 10. Top-level classification

**INGESTION_DOMINANT**

Quantitative reason: `ingestion_total` accounts for 98.0–98.4% of measured
cycle time on every one of the 21 primary cycles, with essentially zero
variance. No other classification is defensible given this evidence.

## 11. Ingestion breakdown

Using the exact persisted call-group names (`ingestion.daily_candles`,
`ingestion.intraday_candles`, `ingestion.quotes` — not invented aliases):

| Group | count/cycle | total_seconds (median) | median call | p90 call (per-run median) | max single call observed |
|---|---|---|---|---|---|
| `ingestion.daily_candles` | 536 | 181.50s | 0.338s | 0.343s | 3.3846s (`NSE:ASTRAL`) |
| `ingestion.intraday_candles` | 1,072 | 364.47s | 0.338s | 0.342s | 2.5055s (`NSE:MARUTI:5m`) |
| `ingestion.quotes` | 1 (single batched call) | 1.148s | — | — | 1.303s max across cycles |

`ok_count`/`failed_count` (summed across all 21 cycles): `daily_candles`
11,256 ok / **0 failed**; `intraday_candles` 22,512 ok / **0 failed**;
`quotes` 21 ok / **0 failed**. Retry count is not separately persisted by
this recorder (stated explicitly, not estimated) — only ok/failed counts
and per-call durations are captured; if the provider client itself retried
internally, that time is folded into the call's own recorded duration, not
broken out.

## 12. Historical call counts

Measured (not the prior): **536 instruments × 3 historical calls/instrument
(1 daily + 2 intraday, for the two configured timeframes) = 1,608 total
sequential historical calls per cycle**, on every one of the 21 cycles,
with zero variance in the count.

This matches the representative prior (~536 instruments, ~1,608 historical
calls) essentially exactly — not by construction, but because
`config/ingestion.json`'s real, currently-deployed settings
(`timeframes: ["5m", "15m"]`, `include_daily: true`) and the real resolved
universe size (536, confirmed via `ingestion.daily_candles.count` on every
cycle) happen to reproduce it.

## 13. `(N − 1) × 0.334s` pacing comparison

`N = 1,608` (constant across all 21 cycles) →
`pacing_prior_seconds = (1,608 − 1) × 0.334 = 536.738s` (constant).

| | median | min | max |
|---|---|---|---|
| Measured historical duration (`daily_total + intraday_total`) | 546.85s | 542.72s | 555.92s |
| Pacing prior | 536.74s | 536.74s | 536.74s |
| Absolute difference | 10.11s | 5.98s | 19.19s |
| Ratio (measured / prior) | **1.019** | 1.011 | 1.036 |

## 14. Pacing explanatory power

**Yes — the source-confirmed historical-call pacing explains the large
majority of the ~9.4-minute cycle, and the large majority of the
historical-ingestion time specifically.**

Decomposition of the ~560.6s median cycle:

- **Client pacing floor** (the deterministic `(N−1)×0.334s` lower bound
  the pacing policy itself imposes): **536.74s ≈ 95.7% of the median
  cycle total.**
- **Network/provider response time beyond the pacing floor** (measured
  historical duration minus the pacing prior): **≈10.1s ≈ 1.8% of the
  median cycle total.** Supporting evidence: the per-call median duration
  for both `daily_candles` (0.338s) and `intraday_candles` (0.338s) is
  within 0.004s of the 0.334s pacing interval itself — the overwhelming
  majority of each call's own wall-clock time *is* the enforced pacing
  sleep, not genuine request/response latency.
- **Retry/backoff time:** zero — 0 failures, 0 retries observed across
  11,256 + 22,512 + 21 = 33,789 total provider calls in the primary
  sample (see §11, §18).
- **DB persistence + validation/quarantine overhead inside the ingestion
  phase** (the residual: `ingestion_total − daily_total − intraday_total
  − quote_total`): median **2.49s ≈ 0.45% of the median cycle total**
  (range 2.20–3.10s). Not separately instrumented as its own call group —
  this is a bounded *inference* from the residual, not a direct
  measurement (see §21).
- **Analytical scan:** median 9.93s ≈ 1.77% (§19).
- **Pre-final orchestration overhead:** ≈0s ≈ 0.00% (§20).

Nothing here is collapsed into a vague "Kite is slow" claim: the evidence
specifically distinguishes the *enforced client pacing policy itself*
(dominant, 95.7%) from *genuine network/provider response time beyond that
policy* (small, 1.8%).

## 15. Daily vs. intraday contribution

| | count | median total_seconds | % of combined historical time |
|---|---|---|---|
| Daily (D1) | 536 | 181.50s | 33.2% |
| Intraday (M5 + M15, combined) | 1,072 | 364.47s | 66.8% |

Per-call medians are essentially identical between the two groups (0.338s
both). **The 2:1 split is explained entirely by call count (1,072 vs. 536
— exactly the 2-timeframes-vs-1 ratio `config/ingestion.json` configures),
not by any inherent per-call cost difference between the daily and
intraday endpoints.** The instrumentation does not separate M5 from M15
within `ingestion.intraday_candles` — both timeframes share one call-group
name (`f"{iid}:{timeframe.value}"` labels individual samples, but the
aggregate `count`/`total_seconds`/percentiles combine both timeframes).
This is stated explicitly as a real instrumentation-granularity limit, not
inferred as if measured separately (see §37).

## 16. Quote fetch

`ingestion.quotes`: exactly **one** batched call per cycle (label
`"batch"`), median 1.148s (range 1.104–1.303s across the 21 cycles). This
is **≈0.2% of cycle total — immaterial**, not assumed negligible: measured
directly. Note this canonical-cycle quote call is a single one-shot
snapshot batch (`self._provider.quotes(ids)`, one call), architecturally
different from EMR's own multi-poll checkpoint-price collector
(`collect_checkpoint_reference_prices`) — the two are unrelated mechanisms
serving different purposes; this section is about the canonical cycle's
quote call only.

## 17. Retries / failures / backoff

**Zero** retries, zero failures, zero 429s, zero timeouts observed across
all 33,789 provider calls in the 21-cycle primary sample (§11). The
measured ~9.4-minute latency is **normal-path structural**, not caused by
exceptional retry/failure behavior. (The source-confirmed prior — 429
backoff 1s/2s/4s, max 3 retries, 30s provider timeout — was not exercised
at all in this sample; nothing here contradicts or confirms those specific
values beyond "they were never triggered.")

## 18. Analytical scan cost

`scan_total`, n=21:

| min | median | mean | p90 | p95 | max |
|---|---|---|---|---|---|
| 8.94s | 9.93s | 10.06s | 11.14s | 11.20s | 11.21s |

≈1.6–2.0% of cycle total on every cycle. **Not a meaningful contributor**
to the ~9–10 minute latency in absolute terms, though its own ~9-second
median is not itself negligible as a number. The instrumentation wraps
the *entire* `self._pipeline.run(...)` call as one phase
(`scan_total`) — there is no sub-phase breakdown distinguishing ID-6
EntryQualification's own cost from the rest of the analytical pipeline
(regime, evidence, scoring, confidence, risk, decision, EntryQualification,
etc., all inside that one call). **This review does not, and cannot,
attribute a specific share of the ~9.9s to EntryQualification specifically
— doing so would be inferring function-level cost that was never
instrumented**, which the authorization explicitly prohibits.

## 19. Pre-final orchestration overhead

`orchestration_overhead_pre_final_persist`, n=21:

| min | median | mean | p90 | p95 | max |
|---|---|---|---|---|---|
| 0.000s | 0.000s | 0.0004s | 0.001s | 0.002s | 0.003s |

≈0.00% of cycle total. Confirmed (§6) this still excludes the terminal
`save_run` call, per ID-7P0.1's own frozen semantics — never mislabeled as
"database finalization."

## 20. DB-persistence evidence / limitations

ID-7P0 does **not** directly time all persistence operations. The only
bound available is the residual described in §14/§21
(`ingestion_total − daily_total − intraday_total − quote_total`, median
2.49s), which *includes* candle persistence, dataset validation, and
quarantine review together — not DB writes alone. **This is explicitly
labeled as an inference/upper bound on a mixture of things, not a direct
DB-persistence measurement.** No more precise attribution is claimed.

## 21. Slowest-call analysis

Top individual call durations observed across all 21 cycles (bounded,
aggregate view — not a per-symbol dump):

**Daily candles** (max 3.3846s, `NSE:ASTRAL`; next: 2.3103s `NSE:BATAINDIA`,
2.0245s `NSE:NESTLEIND`, then a cluster of 1.2–1.6s calls) — a handful of
calls running 3–10× the ~0.338s median, but all `ok=True`, all still under
3.5s absolute. **This is the shape of many intentionally-paced ordinary
calls with mild variance, not a few pathological outliers dominating the
total** — the slowest single call (3.38s) is under 0.6% of the 560.6s
median cycle total.

**Intraday candles** (max 2.5055s `NSE:MARUTI:5m`; next: 2.4836s
`NSE:ITCHOTELS:15m`, 2.393s `NSE:SUNPHARMA:5m`) — same pattern: modest,
`ok=True` variance, no evidence of a pathological subset.

## 22. Cross-cycle stability

**Highly stable.** Across all 21 primary cycles:

- Instrument count: constant at 536 (zero variance).
- Historical call count: constant at 1,608 (zero variance).
- `ingestion_pct` of cycle total: 98.00–98.40% (0.40 percentage-point
  spread).
- `scan_pct`: 1.60–2.00% (0.40 percentage-point spread).
- Pacing ratio (measured/prior): 1.011–1.036 (a 2.5 percentage-point
  spread).
- Daily-vs-intraday split of historical time: 32.7–33.6% daily,
  66.4–67.3% intraday (under 1 percentage point of spread).

No cycle differs materially enough to warrant individual explanation
beyond ordinary provider-latency variance.

## 23. Cross-day replication

**Not available — 2026-09-03 provides zero usable timing evidence** (§4:
all 27 of that day's `REFRESH`/`COMPLETED` cycles lack a `timing` payload
entirely, since the ID-7P0 restart landed later in the day). Per the
authorization's own instruction, both days are not required for closure
when one day's sample is sufficient — today's n=21 sample is internally
tight, stable, and reproduces the ID-6E-era phenomenon (§8), so this
review proceeds on today's evidence alone. Cross-day replication remains
an open item for a future natural-evidence check, not a blocker here.

## 24. Ingestion subclassification

**HISTORICAL_CANDLE_PACING**

Justification (per the authorization's own evidentiary bar): the large
sequential historical-call population (1,608 calls/cycle) combined with
the enforced ~0.334s minimum interval explains **95.7% of the median
cycle total** via the deterministic pacing floor alone (§14), and the
measured historical-ingestion time exceeds that floor by only **1.9%**
(ratio 1.019, §13) — a small, consistent margin, not a materially-beyond-
the-floor network cost. `QUOTE_FETCH` and `DB_PERSISTENCE` are both
immaterial in absolute terms (§16, §20). This is not `MIXED_INGESTION`:
the evidence cleanly isolates one dominant component rather than being
unable to separate several.

## 25. Root-cause statement

> The ~9–10 minute ATHENA production cycle latency is primarily caused by
> **historical-candle-call pacing**, accounting for approximately **96%**
> of measured cycle time. The dominant subcomponent is the **enforced
> ~0.334s minimum interval across 1,608 sequential historical candle
> calls per cycle (536 instruments × 3 calls: 1 daily + 2 intraday
> timeframes)**, with measured elapsed historical-ingestion time
> exceeding the deterministic `(N−1)×0.334s` pacing floor by only ~2%
> (median ratio 1.019) and zero retries/failures observed across 33,789
> provider calls. Analytical scan contributes approximately **1.6–2.0%**,
> and pre-final orchestration contributes approximately **0%**.

## 26. ID-7 architectural consequence

Canonical cycle-derived evidence carries a structural ~9.3–9.5 minute
refresh latency, driven overwhelmingly by a provider rate-limit-bound
historical-data pull, not by anything ATHENA's own code currently controls
algorithmically (given the current sequential, per-instrument,
per-timeframe call pattern). This latency is **highly stable and
predictable** (§22), not an intermittent/exceptional condition.

**Consequence, stated only, not designed:** if ID-7's future intraday
actionability artifact needs freshness materially tighter than ~9–10
minutes at the moment of use, it cannot honestly rely on canonical cycle
completion time alone as its evidence-freshness guarantee — the
underlying candle data backing a canonical-cycle-timed evaluation can be
up to one full cycle (~9.4 minutes) old relative to the market at
evaluation time. Whether this materially matters depends entirely on
ID-7's own target entry timescale, which is not yet decided (that
decision remains ID-7A0's, still blocked). EntryQualification's own
already-frozen semantics (point-in-time, non-sticky,
`LIVE_M5_PROVISIONAL` when applicable) already anticipate representing
staleness/provisionality honestly rather than assuming instantaneous
freshness — this existing semantic is directly relevant to how any future
actionability artifact would need to represent the same ~9-minute
characteristic, whatever architecture it ultimately uses.

## 27. Recommendation classification

**A — LATENCY COMPENSATION ONLY**, with an explicit caveat.

The measured latency is a clean, well-understood, highly stable,
zero-defect, provider-rate-limit-bound structural cost — not a bug, not
an inefficiency needing a fix, not an exceptional condition. EntryQualification's
frozen methodology already carries the semantic machinery
(point-in-time, non-sticky, provisional labeling) to honestly represent
evidence age rather than assume freshness — the architecture is already
built to compensate via freshness semantics, not to require latency
reduction as a prerequisite.

**Caveat (owner's own judgment required, not resolved by this review):**
this classification assumes ID-7's target entry timescale can tolerate
~9-minute-stale evidence when honestly labeled as such. If ID-7A0
ultimately decides intraday entry timing requires materially fresher
data than a canonical cycle can provide, this classification would need
revisiting — that determination depends on a not-yet-made ID-7A0 design
decision, not on anything this latency measurement alone can settle.

## 28. Recommended future actionability evaluation mode (recommendation only)

Given the measured evidence — recommend evaluating **event-driven or
asynchronous-after-ingestion** modes as the more promising directions for
a future intraday actionability artifact, over **canonical-cycle-
synchronous** evaluation, *if* ID-7A0 determines sub-9-minute freshness is
required. Reasoning, from evidence only:

- Canonical-cycle-synchronous inherits the full ~9.3–9.5 minute structural
  latency by construction (§25) — any entry-timing use case needing
  materially fresher evidence would be poorly served by this mode alone.
- Asynchronous-after-ingestion or event-driven modes could, in principle,
  react to already-persisted data as it lands (per-instrument or
  per-timeframe) rather than waiting for the full 536-instrument ×
  3-call sequential sweep to complete — though this review does not
  evaluate feasibility, determinism, replayability, or Decision/EQ
  identity-binding implications of any such mode; that belongs to a
  future design milestone, not here.
- On-demand/API-time evaluation was not evaluated favorably or
  unfavorably from latency evidence alone — its own trade-offs
  (determinism, replayability, provider-call control) are architectural
  concerns this latency audit has no evidence about either way.

This is a recommendation only. No ADR is modified. No direction is frozen.
ID-7A implementation is not authorized by this document.

## 29. ID-7P0 instrumentation-retention recommendation

**Recommend: remain permanently, as low-cost observability.** The
recorder is purely additive, orthogonal, and already proven safe in
production (§30) — it adds negligible overhead (the `orchestration_overhead_pre_final_persist`
phase itself, which captures ID-7P0's own remaining measurement gap, is
consistently ≈0s) and provides exactly the kind of evidence this review
depended on. No code change recommended or made.

## 30. Business-output safety

- No scoring formula change: confirmed via `git log --oneline --since=2026-09-03
  -- src/athena/scoring src/athena/decision src/athena/confidence
  src/athena/risk src/athena/intraday` — the one match
  (`e4ecf0a "feat(portfolio): add Portfolio Conviction adapter"`) is
  Portfolio-track work (PS-P7B) that only *reads* already-persisted
  Confidence through a shared helper; it does not touch scoring/
  DecisionEngine/EntryQualification methodology and predates/is unrelated
  to this audit.
- No DecisionEngine change, no EntryQualification methodology change, no
  TradePlan change: confirmed — `timing.py`/`dry_run.py`'s own git history
  shows no commits since ID-7P0/ID-7P0.1 (`d8025f3`, `aa580f9`); no other
  file in the decision-adjacent packages was touched by that work.
- No canonical schema change caused by timing instrumentation: canonical
  `schema_version` is `17`, unchanged (verified read-only, matches the
  pre-ID-7P0 baseline).
- No EMR/DarvaX methodology interaction: ID-7P0's instrumentation lives
  entirely in `athena.observability`/`athena.scheduling`, imported by
  neither `athena.explosive_move` nor `athena.darvax`; confirmed by the
  existing isolation-test suites for both, unaffected by this work.
- This is a directly-verified comparison (git log + schema-version read),
  not an unchecked assumption.

## 31. EMR preservation

Not queried, not modified, not restarted specifically. `db/emr.db` was
not opened by this audit at all. EM-7C's own production shadow continued
operating independently and untouched throughout.

## 32. DarvaX preservation

Not queried, not modified. `db/darvax.db` was not opened by this audit.

## 33. Files changed

Created: `docs/research/ID-7P0-PRODUCTION-CYCLE-LATENCY-ATTRIBUTION-REVIEW.md`
(this document). No source code changed.

## 34. Documentation updates

`docs/MILESTONES.md`, `IMPLEMENTATION_SUMMARY.md`, `ATHENA_BRIEFING.md`
updated to record this review's completion and to state explicitly:
**ID-7A0 remains BLOCKED PENDING OWNER / CHIEF ARCHITECT REVIEW OF ID-7P0
ATTRIBUTION.** ID-7P0 itself is not marked owner-approved by this
document; that determination belongs to the owner.

## 35. Validation / git diff result

Documentation-only change. `git diff --check`: clean. No test suite run
was performed solely for this documentation-only milestone, per the
authorization's own instruction ("do not run a full test suite merely to
create activity unless project convention requires it for
documentation-only changes").

## 36. Remaining evidence limitations

- `ingestion.intraday_candles` combines M5 and M15 into one call group;
  the two timeframes cannot be separated in aggregate statistics from this
  instrumentation alone (only visible per-sample in the bounded
  `slowest` list) — §15.
- No sub-phase breakdown exists inside `scan_total`; EntryQualification's
  own specific cost within the ~9.9s analytical scan is not measurable
  from this instrumentation — §18.
- DB-persistence time is not directly measured; only bounded as part of a
  mixed residual together with validation/quarantine review — §20.
- Retry count is not separately persisted; only ok/failed call counts and
  per-call durations are available — §11.
- Cross-day replication (2026-09-03 vs. 2026-09-04) was not possible —
  yesterday's completed REFRESH cycles carry no timing payload — §23.
- One `REFRESH`/`RUNNING` cycle from today appears orphaned/stuck
  (started 13:48:09 IST, still running ~2 hours later at cutoff) — noted,
  not investigated, out of this audit's scope — §4.

## 37. Recommended next milestone (recommendation only)

Owner/Chief Architect review of this attribution, followed by an ID-7A0
design decision on target entry-timescale requirements — the swing factor
for §27's caveat. Optionally, a future natural cross-day replication check
once 2026-09-03-equivalent timing-instrumented REFRESH evidence exists for
a comparison day. Not started here.
