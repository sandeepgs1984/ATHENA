# EM-5 Track B Tuesday Readiness Checklist

**Target session:** 2026-09-01
**Status:** Ready for pre-09:20 live-session preflight.
**Scope:** Operational checklist only; no methodology change.

## Verified Readiness Facts

- ATHENA calendar status for 2026-09-01: `NORMAL`.
- Frozen sample: 9 equities, unchanged.
- Frozen checkpoints: `09:20`, `09:30`, `09:45`, `10:00`, `10:30`,
  `11:00`, `12:00`, `13:00`, `14:00` IST.
- Observation window: 300 seconds.
- Request budget: 81 provisional capture requests plus 9 settlement requests
  later, 90 total across the full two-phase campaign.
- Same-day settlement guard: not likely settled.
- No stale Tuesday Track B artifacts found during readiness inspection.

## Frozen Sample

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

## Pre-09:20 Operator Actions

1. Confirm the worktree is the intended ATHENA checkout.
2. Confirm local time handling is IST-aware.
3. Run the existing `run_preflight` path for 2026-09-01: ATHENA calendar,
   Kite auth/catalog resolution for the frozen nine symbols, and disk space.
4. Confirm no stale Tuesday artifacts exist before capture.
5. Start the existing `run_capture_phase` before `09:20` IST and rerun it
   after each checkpoint as needed.
6. Preserve every raw provider response exactly as written by the existing
   Track B tooling.
7. Record any missed checkpoint beyond 300 seconds as `NOT_OBSERVED_LIVE`.
8. Do not run settlement comparison during the live session.

## Prohibitions

- No ID-5B artifact use or substitution.
- No database writes.
- No timestamp normalization, flooring, ceiling, rounding, nearest-match
  mapping, resampling, forward-fill, synthetic candles, or quote substitution.
- No EM-6, UI, canonical ATHENA scoring/confidence/risk/Decision/TradePlan,
  DarvaX, or broker/order behavior changes.
