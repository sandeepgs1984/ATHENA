# EM-5 Track B Live M5 Capture Evidence

**Date:** 2026-08-31
**Track:** Explosive Move Radar (EMR)
**Milestone:** EM-5 Track B — live provisional-vs-settled M5 semantics
**Status:** Monday live capture not observed; another live session required.

## Scope

Frozen EM-5 Track B canary:

| Instrument | Liquidity bucket |
|---|---|
| `NSE:IDEA` | high |
| `NSE:OLAELEC` | high |
| `NSE:YESBANK` | high |
| `NSE:BBTC` | medium |
| `NSE:IRCTC` | medium |
| `NSE:RITES` | medium |
| `NSE:JSWDULUX` | low |
| `NSE:ABBOTINDIA` | low |
| `NSE:HONAUT` | low |

This is a different frozen sample from ID-5B's canary and cannot be
substituted with ID evidence.

## Artifact Inspection

Repository artifact inspection found no EM-5 Track B Monday 2026-08-31 live
capture files under `artifacts/`.

Existing EMR artifacts found:

- `artifacts/research/em5_diagnostic/` — the earlier 2026-08-28
  checkpoint-price parity diagnostic.
- No `artifacts/live/em5`, `artifacts/research/em5_track_b`, or equivalent
  Monday Track B live-M5 capture directory was present.

Existing ID artifacts found:

- `artifacts/live/id5b/2026-08-31/` — ID-5B's separate 5-instrument canary.
  These artifacts are not EM-5 Track B evidence.

## Checkpoint Status

At local verification time `Mon Aug 31 15:39:33 IST 2026`, every frozen EM-5
Track B checkpoint had elapsed by more than the approved 300-second live
observation window:

| Checkpoint | Status |
|---|---|
| `09:20` | `NOT_OBSERVED_LIVE` |
| `09:30` | `NOT_OBSERVED_LIVE` |
| `09:45` | `NOT_OBSERVED_LIVE` |
| `10:00` | `NOT_OBSERVED_LIVE` |
| `10:30` | `NOT_OBSERVED_LIVE` |
| `11:00` | `NOT_OBSERVED_LIVE` |
| `12:00` | `NOT_OBSERVED_LIVE` |
| `13:00` | `NOT_OBSERVED_LIVE` |
| `14:00` | `NOT_OBSERVED_LIVE` |

No Kite/provider request was made while producing this note. No raw capture
artifact was fabricated after the live window.

## Conclusion

The required Monday 2026-08-31 EM-5 Track B live evidence was not captured.
Historical data cannot reconstruct it, and ID-5B evidence cannot satisfy the
EMR frozen sample. EM-5 remains `COMPLETE PENDING CANARY`, blocked on a fresh
live-session Track B capture followed by the already-gated settled-provider
comparison.

Next required action: run the existing `em5_track_b_capture_cli.py` operator
flow during the next real NSE live session, subject to calendar and Kite
preflight, without changing the frozen methodology.
