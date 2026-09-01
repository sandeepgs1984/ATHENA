# EM-5 Track B Tuesday Live M5 Capture Evidence

**Date:** 2026-09-01
**Track:** Explosive Move Radar (EMR)
**Milestone:** EM-5 Track B — live provisional-vs-settled M5 semantics
**Status:** Live capture phase owner-approved; settled-provider comparison
complete; EM-5 Track B.1 zero-off-grid contract-gap correction implemented and
owner-accepted. Corrected Track B classification:
`NO_OFF_GRID_PROVISIONAL_OBSERVED`. Final Section 14 canary PASS; EM-5 ready
owner-approved / closed 2026-09-01.

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

Frozen checkpoints: `09:20`, `09:30`, `09:45`, `10:00`, `10:30`,
`11:00`, `12:00`, `13:00`, `14:00` IST.

This is EMR-only evidence. It is distinct from ID-5B's five-instrument
canary and must not be substituted into the ID track.

## Preflight

Command used:

```bash
caffeinate -dimsu env PYTHONPATH=src python3 -m athena.data.em5_track_b_capture_cli unattended --session-date 2026-09-01
```

Observed preflight result from the runner:

- ATHENA session type: `NORMAL`.
- Frozen catalog resolution: passed (`resolved_symbols=22` in the provider
  instrument map; the nine frozen Track B symbols were available for capture).
- Kite authentication/provider access: passed.
- Disk free at start: `62.06707000732422` GiB.
- Workstation mechanism: macOS `caffeinate` plus the existing EM-5 Track B
  unattended runner.
- Settlement comparison: not run.

Before the live run, a stale pre-live artifact directory containing fake
provider placeholder files was found under
`artifacts/live/em5_track_b/2026-09-01/`. It was preserved, not deleted, by
moving it to
`artifacts/live/em5_track_b/quarantine/2026-09-01-fake-prelive-artifacts-20260901T0857IST/`.
The live capture then started from a clean `2026-09-01` directory.

## Live Capture Results

Final live artifact directory:
`artifacts/live/em5_track_b/2026-09-01/`.

Manifest:
`artifacts/live/em5_track_b/2026-09-01/em5-track-b-20260901__manifest.json`.

Manifest SHA-256 after final live capture:
`b0f46dab7233df61ec4c9e606758f455e03cda064b19cfff7a72ccfa480573c4`.

Final manifest integrity:

- Raw capture files in manifest: 81.
- Raw capture files present on disk: 81.
- Missing manifest paths: 0.
- Extra raw files in final live directory: 0.
- Provider names: `kite` for 81/81 files.
- Successful raw captures: 81/81.
- Provider/raw artifact failures: 0.
- Total raw candles captured across the 81 files: 1,768.
- Off-grid `ts_open` values observed in raw live files: 0.
- `NOT_OBSERVED_LIVE` checkpoints: 0.

## Checkpoint Table

| Checkpoint | Final manifest status | Request timestamp | Raw files | Candle count range |
|---|---|---|---:|---:|
| `09:20` | `ALREADY_CAPTURED` | `2026-09-01T09:20:00.008346+05:30` | 9 | 1-1 |
| `09:30` | `ALREADY_CAPTURED` | `2026-09-01T09:30:03.114684+05:30` | 9 | 3-4 |
| `09:45` | `ALREADY_CAPTURED` | `2026-09-01T09:45:06.292263+05:30` | 9 | 6-7 |
| `10:00` | `ALREADY_CAPTURED` | `2026-09-01T10:00:09.272915+05:30` | 9 | 10-10 |
| `10:30` | `ALREADY_CAPTURED` | `2026-09-01T10:30:12.485554+05:30` | 9 | 16-16 |
| `11:00` | `ALREADY_CAPTURED` | `2026-09-01T11:00:15.781422+05:30` | 9 | 21-22 |
| `12:00` | `ALREADY_CAPTURED` | `2026-09-01T12:00:36.042947+05:30` | 9 | 34-34 |
| `13:00` | `ALREADY_CAPTURED` | `2026-09-01T13:00:39.294704+05:30` | 9 | 46-46 |
| `14:00` | `CAPTURED` | `2026-09-01T14:00:42.692985+05:30` | 9 | 58-58 |

`ALREADY_CAPTURED` means the final manifest was written by a later
idempotent runner pass after the raw checkpoint files already existed. It
does not mean those checkpoints were missed or reconstructed.

## Runtime Notes

- The existing unattended runner was used; no new operational wrapper was
  added for the live session.
- The runner remained alive through the owner travel window and continued
  after the laptop was reopened, preserving existing raw files and adding
  only due checkpoint files.
- The runner stopped after the final `14:00` pass.
- No raw artifact was modified, rounded, resampled, normalized, repaired, or
  synthesized after capture.
- No `db/athena.db` or `db/emr.db` writes were performed by Track B.
- No ID-5B settlement, EM-5 settlement, EM-6, UI, DarvaX, scoring,
  confidence, risk, Decision, TradePlan, scanner-methodology, broker, or
  order behavior work was performed.

## Settled-Provider Comparison

Owner authorization to run the existing Track B settlement comparison was
received on 2026-09-01. The existing settlement-readiness guard did not pass
without override because the session was still 0 days old relative to the local
date and `MINIMUM_DAYS_BEFORE_LIKELY_SETTLED = 21`. The owner authorization
therefore used the implementation's already-defined explicit `force=True`
override. No new override was added.

Execution path:

`src/athena/data/em5_track_b_capture_cli.py::run_settlement_comparison_phase`

Settlement artifact:

`artifacts/live/em5_track_b/2026-09-01/em5-track-b-20260901__settlement_comparison.json`

Settlement artifact SHA-256:
`974531de8703982fcab49d15924b21e986728e0fd4c2759b034af36f6345a0a1`.

Recorded settlement metadata:

- Provider: `kite`.
- Settlement request timestamp:
  `2026-09-01T20:06:46.140654+05:30`.
- Owner override used: `true`.
- Minimum-days guard passed without override: `false`.
- Preflight session type: `NORMAL`.
- Resolved symbol count: 22.
- Disk free at settlement preflight: `59.88642501831055` GiB.

Comparison inventory recorded by the existing implementation:

| Instrument | Compared provisional rows |
|---|---:|
| `NSE:ABBOTINDIA` | 197 |
| `NSE:BBTC` | 196 |
| `NSE:HONAUT` | 196 |
| `NSE:IDEA` | 196 |
| `NSE:IRCTC` | 196 |
| `NSE:JSWDULUX` | 196 |
| `NSE:OLAELEC` | 198 |
| `NSE:RITES` | 196 |
| `NSE:YESBANK` | 197 |

Total comparison rows recorded by the report inventory: 1,768.

Original frozen Track B classification field before B.1: `null`.

Reason: Tuesday's live capture had 0 off-grid raw `ts_open` values. The frozen
Track B classifier classifies only off-grid provisional rows into one of:
`TIMESTAMP_ONLY_PROVISIONAL_DRIFT`,
`PROVISIONAL_OHLCV_ALSO_CHANGES`, or `MAPPING_AMBIGUOUS`. With no off-grid
rows, the existing accepted implementation leaves classification unset rather
than inventing a fourth outcome or silently mapping ID-5B's CASE framework onto
EM-5.

Fields not persisted by the existing report:

- settled full-session candle counts;
- per-row settled candles;
- field-by-field OHLCV differences for on-grid provisional rows;
- exact/unique/ambiguous/unmatched totals over all on-grid rows.

Those values were not reconstructed with additional provider requests after the
run.

## EM-5 Track B.1 Correction

Owner review accepted the original `classification=null` result as a
state-space completeness gap: the frozen three-label classifier had no outcome
for a complete canary with zero off-grid provisional rows. Track B.1 adds the
explicit observational outcome:

`NO_OFF_GRID_PROVISIONAL_OBSERVED`

This outcome may be emitted only when immutable live-capture evidence proves:

- all required symbols were observed;
- all required checkpoints were observed;
- all raw captures succeeded;
- zero eligible off-grid provisional `ts_open` rows were observed.

It preserves the existing three off-grid outcomes unchanged:
`TIMESTAMP_ONLY_PROVISIONAL_DRIFT`,
`PROVISIONAL_OHLCV_ALSO_CHANGES`, and `MAPPING_AMBIGUOUS`.

Raw-only replay of the Tuesday evidence after B.1:

- Required symbols: 9.
- Required checkpoints: 9.
- Expected capture files: 81.
- Observed capture files: 81.
- Successful capture files: 81.
- Failed capture files: 0.
- Provisional rows: 1,768.
- Off-grid provisional rows: 0.
- Missing files: 0.
- Missing required symbol/checkpoint pairs: 0.
- Extra symbol/checkpoint pairs: 0.
- Duplicate symbol/checkpoint pairs: 0.

Corrected Track B classification:
`NO_OFF_GRID_PROVISIONAL_OBSERVED`.

No provider request was made for this replay. The existing settlement artifact
was not regenerated and still records the pre-B.1 `classification=null` result.

## Track B Interpretation

Observation: the frozen Tuesday Track B canary captured all 9 checkpoints and
all 9 symbols with 81/81 real Kite raw files, 0 provider failures, 1,768 raw
candles, and 0 off-grid raw `ts_open` values. The settlement report completed
through the existing implementation. Before B.1, that produced
`classification=null`; after B.1, the raw-only live evidence classifies as
`NO_OFF_GRID_PROVISIONAL_OBSERVED`.

Inference: this specific canary did not observe the provisional off-grid
phenomenon. It does not demonstrate timestamp-only provisional drift,
provisional OHLCV changes on off-grid rows, or ambiguous off-grid mapping. It
also does not prove Kite never returns off-grid current-session M5 rows, does
not invalidate ID-5B's independent CASE B finding, and does not prove all
current-session M5 data equals settled historical truth.

Engineering recommendation: the corrected B.1 outcome is sufficient to clear
the specific `CANARY_BLOCKED_LIVE_M5_SEMANTICS` blocker for this frozen canary:
a complete, successful, predeclared live canary observed zero instances of the
defect it was designed to characterize. This does not relax Section 14's
production canary requirements.

## Track B.1 Verification

Focused tests:

`tests/data_layer/test_live_m5_provisional_settlement_diagnostic.py`,
`tests/data_layer/test_em5_track_b_capture_cli.py`

Result: 44 passed.

`git diff --check`: clean during implementation verification.

Artifact integrity after Track B.1:

- Tuesday manifest SHA-256:
  `b0f46dab7233df61ec4c9e606758f455e03cda064b19cfff7a72ccfa480573c4`.
- EM-5 settlement artifact SHA-256:
  `974531de8703982fcab49d15924b21e986728e0fd4c2759b034af36f6345a0a1`.
- All 81 raw capture files were byte-identical before and after B.1
  verification.

The full suite was not rerun because this is a narrow Track B diagnostic
state-space correction and the focused suite covers the relevant
classification, completeness, deterministic replay, and artifact-safety
branches. FINAL_TEST was not read, rerun, inspected, or used.

## Remaining Work

EM-5 owner approval / closure is recorded as of 2026-09-01. Do not start EM-6,
EM-7, EM-8, or ID-6 from this evidence note.

## Owner Review

Owner review approved the Tuesday 2026-09-01 live capture phase. Track B.1
corrected the zero-off-grid state-space gap, owner accepted the correction, and
the Tuesday evidence is classified as `NO_OFF_GRID_PROVISIONAL_OBSERVED`.
The specific `CANARY_BLOCKED_LIVE_M5_SEMANTICS` blocker is cleared for this
frozen canary.

Final EM-5 validation then ran the unchanged Section 14 full nine-checkpoint
production canary against `athena_core` / 2026-08-28 via
`run_em5_production_canary()`: PASS, 518/518 mature instruments, 9,324/9,324
all-required-fields-known at every checkpoint, 99% floor PASS, relative
baseline PASS, frozen artifact hashes PASS, checkpoint-boundary regression
PASS, freshness PASS, hard eligibility PASS, zero provider/network calls PASS,
and replay determinism PASS. Owner final approval on 2026-09-01 closes EM-5.
EM-6 and ID-6 remain not started pending separate owner authorization.
