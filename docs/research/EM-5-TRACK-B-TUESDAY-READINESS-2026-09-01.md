# EM-5 Track B Tuesday Readiness Checklist

**Target session:** 2026-09-01
**Status:** Live capture phase owner-approved; settled-provider comparison
pending explicit owner authorization.
**Scope:** Operational checklist plus unattended orchestration; no methodology
change.

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
- Unattended runner: available via the existing Track B module; it preflights
  once, waits efficiently, captures each frozen checkpoint, and stops after
  the final 14:00 capture without settlement.

## Live Capture Outcome

The authorized Tuesday run completed on 2026-09-01 using the existing
unattended runner under `caffeinate`. Final evidence is recorded in
`docs/research/EM-5-TRACK-B-LIVE-M5-CAPTURE-2026-09-01.md`.

- Final raw live directory:
  `artifacts/live/em5_track_b/2026-09-01/`.
- Manifest:
  `artifacts/live/em5_track_b/2026-09-01/em5-track-b-20260901__manifest.json`.
- Raw capture files: 81/81.
- Provider: `kite` for 81/81 files.
- Provider failures: 0.
- `NOT_OBSERVED_LIVE` checkpoints: 0.
- Off-grid `ts_open` values in raw live files: 0.
- Settlement comparison: not run.

Owner review approved the live capture phase only. EM-5 remains
`COMPLETE PENDING SETTLED COMPARISON`.

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
3. Confirm no stale Tuesday artifacts exist before capture.
4. Start the unattended runner before `09:20` IST:

```bash
PYTHONPATH=src python3 -m athena.data.em5_track_b_capture_cli unattended --session-date 2026-09-01
```

5. Leave that process running until it exits after the 14:00 capture pass.
6. Preserve every raw provider response exactly as written by the existing
   Track B tooling.
7. Record any missed checkpoint beyond 300 seconds as `NOT_OBSERVED_LIVE`.
8. Do not run settlement comparison during the live session.

## Unattended Workstation Requirements

- Keep the Mac awake. Closing the lid normally sleeps a MacBook unless it is
  docked with power/external display settings that prevent sleep.
- Use power adapter and stable network.
- Keep the terminal session open; closing the terminal can terminate the
  foreground process.
- Prefer running under macOS `caffeinate` for this one-shot live capture:

```bash
caffeinate -dimsu env PYTHONPATH=src python3 -m athena.data.em5_track_b_capture_cli unattended --session-date 2026-09-01
```

- Around 11:20, verify the terminal is still printing wait/capture progress
  and that the manifest exists at
  `artifacts/live/em5_track_b/2026-09-01/em5-track-b-20260901__manifest.json`.
- After 14:00, inspect the manifest and raw JSON files in
  `artifacts/live/em5_track_b/2026-09-01/`.

## Prohibitions

- No ID-5B artifact use or substitution.
- No database writes.
- No timestamp normalization, flooring, ceiling, rounding, nearest-match
  mapping, resampling, forward-fill, synthetic candles, or quote substitution.
- No EM-6, UI, canonical ATHENA scoring/confidence/risk/Decision/TradePlan,
  DarvaX, or broker/order behavior changes.
