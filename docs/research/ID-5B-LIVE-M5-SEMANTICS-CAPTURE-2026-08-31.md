# ID-5B Live M5 Semantics Capture Evidence

**Date:** 2026-08-31
**Track:** Intraday Intelligence (ID)
**Milestone:** ID-5B — Live Current-Session M5 Semantics Canary
**Status:** Live capture phase complete; ID-5B.1 classification correction
owner-approved and closed; settled-provider comparison complete and ready for
owner review.

## Scope

Frozen ID-5B canary:

| Instrument | Role |
|---|---|
| `NSE:NIFTY 50` | benchmark index |
| `NSE:NIFTY BANK` | sector index |
| `NSE:NIFTY IT` | sector index |
| `NSE:RELIANCE` | equity |
| `NSE:INFY` | equity |

Wrapper decision: build a small ID-5B-specific wrapper,
`src/athena/data/id5b_live_m5_semantics_canary.py`, around the shared
read-only primitive `live_m5_provisional_settlement_diagnostic.py`.

Reason: ID-5B needs its own 5-instrument canary, manifest/report names,
request budget, and CASE A/B/C/D mapping. It must not consume EM-5 Track B's
liquidity-bucket sample as substitute evidence, even though both tracks use
the same neutral raw-capture primitive.

## Live Session Verification

Local machine date/time before starting: `Mon Aug 31 09:21:40 IST 2026`.

ATHENA calendar preflight classified `2026-08-31` as `NORMAL`.

Kite catalog/auth preflight passed during the first successful live capture.
Disk preflight passed with approximately 28 GB free.

## Capture Inventory

Artifact directory:

`artifacts/live/id5b/2026-08-31/`

Manifest:

`artifacts/live/id5b/2026-08-31/id5b-live-m5-20260831__manifest.json`

Checkpoint outcome:

| Checkpoint | Status | Notes |
|---|---|---|
| `09:20` | `NOT_OBSERVED_LIVE` | Process started outside the 300-second live evidence window. |
| `09:30` | `ALREADY_CAPTURED` | Captured at `2026-08-31T09:31:46.022797+05:30`. |
| `09:45` | `NOT_OBSERVED_LIVE` | Missed because the first watcher woke just before the exact boundary and the later manual retry was outside the grace window. |
| `10:00` | `NOT_OBSERVED_LIVE` | Same boundary-timing issue; later retry was outside the grace window. |
| `10:30` | `ALREADY_CAPTURED` | Captured at `2026-08-31T10:30:01.028209+05:30`. |
| `11:00` | `ALREADY_CAPTURED` | Captured at `2026-08-31T11:00:01.033105+05:30`. |
| `12:00` | `NOT_OBSERVED_LIVE` | Laptop/sleep interruption resumed after the 300-second live evidence window. |
| `13:00` | `ALREADY_CAPTURED` | Captured at `2026-08-31T13:00:01.031005+05:30`. |
| `14:00` | `CAPTURED` | Captured at `2026-08-31T14:00:01.048233+05:30`. |

Total raw capture files: 25.

No capture file reported `success=false`; no capture file carried a non-null
provider error.

## Raw Timestamp Shape

Structured inventory over the 25 raw files found:

- Tracked instrument/timestamp rows: 288.
- Off-grid provider timestamps: 0.
- Every saved `ts_open` was minute-aligned to the 5-minute grid with zero
  seconds and zero fractional seconds.

This means the 2026-08-31 ID-5B capture did not reproduce the previously
observed off-grid current-session timestamp drift in the sampled windows.

## Same-Day Overlap Stability Evidence

Because each checkpoint captures the full session-open-to-checkpoint window,
same timestamp rows can be compared across later live observations without
any timestamp rounding or nearest matching.

Observed same-day OHLCV changes:

| Timestamp | Instruments changed | Interpretation |
|---|---:|---|
| `09:30` | 5/5 | The boundary candle observed at `09:31:46` changed by later captures. |
| `10:30` | 5/5 | The boundary candle observed at `10:30:01` changed by later captures. |
| `11:00` | 5/5 | The boundary candle observed at `11:00:01` changed by later captures. |

No already-closed, non-boundary row was found to change across the later
same-day captures in this inventory.

ID-5B.1 correction, owner-approved after review: these changed boundary rows
are `FORMING_AT_CAPTURE`, because their actual `request_ts` values occurred
before each candle interval's `ts_open + 5m` completion boundary. Their later
OHLCV changes are useful operational evidence that a boundary/forming candle
is not stable, but they are **not CASE B settlement evidence**.

Corrected same-day reinterpretation against the actual raw artifact request
timestamps:

- `FORMING_AT_CAPTURE`: 15 rows, 15 changed later in same-day overlap.
- `CLOSED_AT_CAPTURE`: 420 rows, 0 changed later in same-day overlap.
- `OFF_GRID_PROVISIONAL`: 0 rows.

Interim reading: current-session boundary/forming M5 rows are not stable OHLCV
evidence. Closed-at-capture canonical rows appeared stable in the same-day
overlap inventory. This is still not the final ID-5B CASE decision because the
milestone's full deliverable requires a later provider-settled comparison.

## Settled-Provider Comparison

Owner authorization to run the manual-gated settled-provider comparison was
received on 2026-09-01. Command path used:

```bash
PYTHONPATH=src python3 -m athena.data.id5b_live_m5_semantics_canary settlement --session-date 2026-08-31 --force
```

Comparison artifact:

`artifacts/live/id5b/2026-08-31/id5b-live-m5-20260831__settlement_comparison.json`

Comparison artifact SHA-256:
`23c6d79e4fd03f78aa57b2a68091647e6fb3b6a1ae8567ddc47f756b8351d5c1`.

The existing ID-5B settlement path persisted the field-by-field comparison
report but did not persist full settled-response candle counts or a settled
request timestamp as first-class metadata fields. The comparison artifact file
mtime was `2026-09-01T15:44:18+0530`; no additional Kite requests were made to
reconstruct missing metadata after the fact.

Final settled comparison evidence:

- Total comparison rows: 723.
- `FORMING_AT_CAPTURE`: 18 rows.
- `CLOSED_AT_CAPTURE`: 705 rows.
- `OFF_GRID_PROVISIONAL`: 0 rows.
- Forming rows changed/no exact settled match: 18.
- Forming rows stable/matched: 0.
- Closed rows stable by unique exact OHLCV mapping: 704.
- Closed rows changed/no exact settled match: 1.
- Ambiguous mappings (`candidate_match_count > 1`): 0.
- Exact-content mappings: 704.

The one closed-at-capture content-change row:

| Instrument | Checkpoint | Provisional timestamp | Request timestamp | Provisional OHLCV | Settled mapping |
|---|---|---|---|---|---|
| `NSE:NIFTY 50` | `14:00` | `2026-08-31T13:55:00+05:30` | `2026-08-31T14:00:01.048233+05:30` | `24060.1, 24060.1, 24043.2, 24043.75, 0` | No exact OHLCV candidate in settled representation |

Matched settled timestamp observations from the comparison report:

| Instrument | Comparison rows | Unique provisional timestamps | Unique matched settled timestamps |
|---|---:|---:|---:|
| `NSE:INFY` | 144 | 57 | 57 |
| `NSE:NIFTY 50` | 144 | 57 | 56 |
| `NSE:NIFTY BANK` | 145 | 58 | 57 |
| `NSE:NIFTY IT` | 145 | 58 | 57 |
| `NSE:RELIANCE` | 145 | 58 | 57 |

Every persisted provisional `ts_open` and every matched settled timestamp was
on the exact 5-minute grid. No off-grid provisional row was observed in this
specific frozen canary.

## Final CASE Status

Final CASE A/B/C/D: `CASE_B_CONTENT_CHANGES`.

Evidence supporting CASE B:

- CASE A is not supported because there were 0 eligible
  `OFF_GRID_PROVISIONAL` rows.
- CASE C is not supported because there were 0 ambiguous mappings and no mix
  of off-grid timestamp-only evidence with content-change evidence.
- CASE D is not supported after settled comparison because one
  `CLOSED_AT_CAPTURE` row had `candidate_match_count == 0`, meaning no exact
  OHLCV candidate existed in the settled representation under the approved
  content-only comparison rule.
- The 18 forming-at-capture rows also had no exact settled match, but they are
  excluded from CASE B/C evidence by ID-5B.1 and are reported only as expected
  forming-candle evolution.

Recommendation: ID-5B can close after owner review with CASE B as the
evidence-supported result. Another live canary is not scientifically necessary
to close ID-5B because the settled comparison found at least one eligible
closed-at-capture content mismatch. This does not prove a universal provider
law; it is enough to preserve a conservative engineering stance toward
current-session M5.

Recommendation for ID-5 overall: if the owner approves this final ID-5B
classification, ID-5 can close. ID-6 should remain not started until that
owner approval is recorded and the next milestone scope is explicitly
authorized.

## Reconciliation With Earlier Root Cause

The earlier ID-5 root-cause work established that Kite can produce off-grid
M5 behavior in relevant historical/current-session circumstances. The Monday
ID-5B frozen five-instrument canary did not reproduce off-grid timestamps: it
observed 0 `OFF_GRID_PROVISIONAL` rows. That absence is evidence about this
specific canary only, not proof that Kite never returns off-grid provisional
M5.

The final settled comparison adds a separate finding: even without off-grid
timestamps in this canary, a row that was already closed at capture can fail
to map by exact OHLCV content to the later settled representation. That is the
specific CASE B evidence for ID-5B.

## Verification

Focused pytest after the settled-provider comparison:

`tests/data_layer/test_id5b_live_m5_semantics_canary.py`,
`tests/data_layer/test_live_m5_provisional_settlement_diagnostic.py`

Result: 30 passed.

`git diff --check`: clean.

Artifact integrity:

- Monday ID-5B manifest SHA-256 remained
  `55d08aaeccccd0249035d6f07e47688e8368289a3374eff132c9a3298be19098`.
- Tuesday EM-5 Track B manifest SHA-256 remained
  `b0f46dab7233df61ec4c9e606758f455e03cda064b19cfff7a72ccfa480573c4`.
- ID-5B settlement report SHA-256:
  `23c6d79e4fd03f78aa57b2a68091647e6fb3b6a1ae8567ddc47f756b8351d5c1`.
- `db/athena.db` mtime (`2026-09-01T15:31:29+0530`) remained older than
  the settlement report mtime (`2026-09-01T15:44:18+0530`), consistent with
  no DB writes by the comparison path.

The full suite was not rerun after settlement because this change set is
documentation plus the owner-authorized evidence run, and broad tests are not
required to validate the raw settlement artifact. Focused ID-5B/raw-diagnostic
coverage passed.

## Remaining Work

Owner review of the settled-provider comparison and CASE B classification.
Do not begin ID-6 until ID-5B has an owner-approved CASE decision and the
owner approves the resulting live-M5 treatment.
