# ID-5B Live M5 Semantics Capture Evidence

**Date:** 2026-08-31
**Track:** Intraday Intelligence (ID)
**Milestone:** ID-5B — Live Current-Session M5 Semantics Canary
**Status:** Live capture phase complete; settlement comparison pending.

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

Interim reading: current-session boundary/forming M5 rows are not stable
OHLCV evidence. This is expected shape for a forming candle and is useful for
ID's operational treatment, but it is not yet the final ID-5B CASE decision
because the milestone's full deliverable requires a later provider-settled
comparison.

## Current CASE Status

Final CASE A/B/C/D: pending.

Current evidence is insufficient to close the milestone because:

- no off-grid provider timestamp was observed in the frozen ID-5B canary;
- same-day overlap proves boundary/forming OHLCV instability, but not the
  final settled provider representation;
- the later settled refetch/comparison has not yet been run.

If the settled comparison confirms that the changed boundary rows remain
different from their first live observations, ID-5B will have direct CASE B
evidence for forming/current-session content changes. If all settled rows
match later same-day observations and no off-grid rows exist, the correct
classification may remain CASE D for the original timestamp-drift question.

## Verification

Focused tests:

`tests/data_layer/test_id5b_live_m5_semantics_canary.py`,
`tests/data_layer/test_live_m5_provisional_settlement_diagnostic.py`,
`tests/data_layer/test_em5_track_b_capture_cli.py`

Result: 40 passed.

Full pytest:

Result: 2941 passed, 1 skipped.

Ruff:

- New ID-5B files: clean.
- Broad `ruff check src tests` still reports unrelated pre-existing issues
  across older modules; not introduced by ID-5B.

## Remaining Work

Run the ID-5B settlement comparison only after the owner confirms the
2026-08-31 provider session should be treated as settled.

Do not begin ID-6 until ID-5B has a reviewed CASE decision and the owner
approves the resulting live-M5 treatment.
