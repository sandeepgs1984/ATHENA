# ID-6B.1 Entry Qualification Evidence Baseline

**Date:** 2026-09-02
**Track:** Intraday Intelligence
**Milestone:** ID-6B.1 - Entry Qualification evidence baseline & policy freeze
**Status:** Evidence baseline complete; ready for owner policy review
**Recommendation:** GO WITH CONDITIONS

This milestone records a read-only settled historical market-time replay. It
does not implement the Entry Qualification engine, does not add persistence,
does not wire workflow, does not add thresholds, does not create UI/API
behavior, does not call providers, and does not write `db/athena.db`.

## 1. Executive Summary

ID-6B.0 is owner-approved / closed. The owner accepted the architecture and
design, but explicitly did not approve the illustrative practical-v0 rule as
methodology. ID-6B.1 therefore measured the existing ID evidence families
before freezing any production rule.

Measured result: the illustrative candidate combination
`VWAP positive AND bullish 5m/15m trend AND (RS support OR RVOL support)`
matched 65 of 370 candidate-checkpoint observations, or 17.57%. It matched
20.00% of sampled `TRADE` observations and 17.00% of sampled `WATCH`
observations. It is selective, but it also flickers: among 74 sampled
instrument/session/type groups with multiple checkpoints, 28 groups
(37.84%) were true and later false at least once.

Recommendation: GO WITH CONDITIONS. The evidence is enough to propose a small
categorical v0 readiness policy for owner approval, but not enough to mark it
as performance-validated. Confirmation should not use `CONFIRMED_BY_POLICY`
in the first engine version unless the owner explicitly accepts a temporal
persistence rule after a broader replay/shadow phase.

## 2. Owner Decisions Recorded From ID-6B.0

- `QUALIFIED` is architecturally permitted, but no positive qualification rule
  was approved by ID-6B.0.
- `DISQUALIFIED_FOR_SESSION` is not used in v0.
- OR15/OR30 remain contextual/support evidence, not mandatory gates.
- WATCH and TRADE use the same intraday evidence methodology unless ID-6B.1
  produces strong evidence for a difference; canonical Decision type is
  preserved.
- `CONFIRMED_BY_POLICY` remains a valid contract value, but the confirmation
  methodology is not approved yet.
- Entry Qualification v0 must not become a weighted vote or mini
  `ScoringEngine`.

## 3. Read-Only Safety

The harness uses a tiny read-only SQLite adapter instead of
`SqliteRepository`, because the normal repository constructor opens a writable
connection for production operation. The adapter opens:

```text
file:db/athena.db?mode=ro
```

and immediately sets:

```text
PRAGMA query_only=ON
```

The replay writes only research outputs under `artifacts/research/id6b1/`.
No provider/network calls are present in the harness.

## 4. Analysis / Replay Architecture

Committed harness:

`src/athena/data/id6b1_entry_qualification_baseline.py`

The harness reconstructs production-equivalent artifacts with existing
engines:

- `SessionContextEngine`
- `IndicatorEngine` for VWAP
- production confluence SMA logic from `owner_validation.py`
- `OpeningRangeEngine`
- `RelativeStrengthEngine`
- `GapEngine`
- `RelativeVolumeEngine`
- `IntradayAnalyticsEngine`

It deliberately labels the output as settled historical market-time replay,
not knowledge-time live reconstruction.

## 5. Historical Sample

Dates:

- 2026-08-26
- 2026-08-27
- 2026-08-28
- 2026-08-31
- 2026-09-01

Checkpoints:

- 09:30
- 09:45
- 10:00
- 11:00
- 13:00
- 14:30

Selection rule: at each session/checkpoint, take the latest same-day Decision
per instrument at or before the checkpoint, keep only `WATCH`/`TRADE`, then
cap deterministically at 10 per type ordered by Decision type and instrument.
This avoids cherry-picking by outcome or by proposed-rule success.

## 6. Sessions / Checkpoints / Candidates Analyzed

- Candidate-checkpoint observations: 370.
- Sessions: 5.
- Checkpoints: 6 per session.
- Distinct instruments: 32.
- WATCH observations: 300 (81.08%).
- TRADE observations: 70 (18.92%).

Fewer than the theoretical 600 observations appeared because several
checkpoints had no available `TRADE` candidates under the deterministic latest
Decision sampling rule.

## 7. Artifact Availability Rates

| Artifact / condition | Count | Percent |
|---|---:|---:|
| SessionContext available | 370/370 | 100.00% |
| IntradaySignalSet constructible | 370/370 | 100.00% |
| Data quality `SUFFICIENT` | 100/370 | 27.03% |
| VWAP available | 370/370 | 100.00% |
| 5m trend available | 370/370 | 100.00% |
| 15m trend available | 370/370 | 100.00% |
| OR15 complete | 370/370 | 100.00% |
| OR30 complete | 260/370 | 70.27% |
| RS available | 370/370 | 100.00% |
| RVOL available | 370/370 | 100.00% |
| Gap available | 370/370 | 100.00% |

The low `SessionDataQualityStatus.SUFFICIENT` rate is the main caution: the
artifacts can usually be constructed, but SessionContext often reported
`EXPECTED_BAR_MISSING` under the exact point-in-time expectations.

## 8. Individual State Distributions

VWAP:

- `ABOVE_VWAP`: 134/370 (36.22%).
- `BELOW_VWAP`: 236/370 (63.78%).

Trend:

- `BULLISH`: 133/370 (35.95%).
- `BEARISH`: 149/370 (40.27%).
- `MIXED`: 88/370 (23.78%).

OR15:

- Formation `COMPLETE`: 370/370 (100.00%).
- Relation `ABOVE_RANGE`: 45/370 (12.16%).
- Relation `INSIDE_RANGE`: 238/370 (64.32%).
- `UPSIDE_BREAKOUT_EVENT`: 79/370 (21.35%).

OR30:

- Formation `COMPLETE`: 260/370 (70.27%).
- Formation `FORMING`: 60/370 (16.22%).
- Formation `INCOMPLETE_DATA`: 50/370 (13.51%).
- Relation `UNAVAILABLE`: 110/370 (29.73%).
- `UPSIDE_BREAKOUT_EVENT`: 48/370 (12.97%).

Relative Strength:

- Stock vs market `OUTPERFORMING`: 147/370 (39.73%).
- Stock vs market `UNDERPERFORMING`: 223/370 (60.27%).
- Stock vs sector `OUTPERFORMING`: 78/370 (21.08%).
- Stock vs sector `UNKNOWN`: 194/370 (52.43%).

RVOL:

- `ABOVE_BASELINE`: 94/370 (25.41%).
- `BELOW_BASELINE`: 276/370 (74.59%).

Gap:

- `GAP_UP`: 254/370 (68.65%).
- `GAP_DOWN`: 114/370 (30.81%).
- `FLAT`: 2/370 (0.54%).

## 9. Simple Combination Prevalence

Overall:

| Combination | Count | Percent |
|---|---:|---:|
| VWAP only | 134/370 | 36.22% |
| Trend only | 133/370 | 35.95% |
| VWAP + trend | 81/370 | 21.89% |
| VWAP + trend + RS | 62/370 | 16.76% |
| VWAP + trend + RVOL | 28/370 | 7.57% |
| VWAP + trend + (RS OR RVOL) | 65/370 | 17.57% |

The RS leg dominates the proposed combination. RVOL adds relatively few
additional matches beyond VWAP+trend+RS in this sample.

## 10. Proposed-v0 Candidate Combination

Neutral research label:

```text
CANDIDATE_POLICY_MATCH
```

Definition for measurement only:

```text
VWAP ABOVE_VWAP
AND trend BULLISH
AND (stock RS support OR RVOL ABOVE_BASELINE)
```

Measured prevalence:

- Overall: 65/370 (17.57%).
- WATCH: 51/300 (17.00%).
- TRADE: 14/70 (20.00%).

This does not approve `QUALIFIED`; it only measures the candidate policy.

## 11. Checkpoint / Time-of-Day Behavior

Candidate-policy match by checkpoint:

| Checkpoint | Count | Percent |
|---|---:|---:|
| 09:30 | 11/60 | 18.33% |
| 09:45 | 19/70 | 27.14% |
| 10:00 | 10/60 | 16.67% |
| 11:00 | 9/60 | 15.00% |
| 13:00 | 10/60 | 16.67% |
| 14:30 | 6/60 | 10.00% |

OR30 materially delays OR30-based confirmation: only 70.27% of observations
had OR30 complete, and 29.73% had OR30 relation unavailable.

## 12. State Transition / Persistence Findings

Among 74 instrument/session/type groups with multiple checkpoints:

- Always false: 39 groups.
- Always true: 3 groups.
- True then later false at least once: 28 groups (37.84%).
- First true appeared most often at 09:30 (11 groups), then 10:00 (9 groups),
  then 11:00 (6 groups).

Observed compressed patterns:

- `false`: 39.
- `true -> false`: 13.
- `false -> true -> false`: 8.
- `false -> true`: 4.
- more oscillatory patterns: 7 combined.

This argues against treating one checkpoint match as strongly confirmed. It
supports researching temporal persistence before using `CONFIRMED_BY_POLICY`.

## 13. Double-Count / Association Findings

Phi coefficients:

- VWAP positive vs trend positive: 0.3848.
- OR15 support vs OR30 support: 0.7439.
- VWAP+trend positive vs any OR support: 0.1824.
- RS support vs RVOL support: 0.1211.
- RS support vs Decision type TRADE: 0.0374.
- RVOL support vs Decision type TRADE: 0.0034.

Interpretation:

- OR15 and OR30 are highly overlapping in this sample.
- VWAP and trend are moderately associated, consistent with the ID-6B.0
  double-count concern.
- RS/RVOL show weak association with each other and almost no association with
  TRADE vs WATCH in this sample, which supports treating them as contextually
  useful rather than Decision-type-specific.

## 14. WATCH vs TRADE Comparison

The candidate combination differs only mildly:

- WATCH: 17.00%.
- TRADE: 20.00%.

VWAP+trend:

- WATCH: 21.67%.
- TRADE: 22.86%.

Trend-only and VWAP-only rates also do not justify separate WATCH/TRADE
methodology in this bounded sample. Preserve the owner decision: same evidence
methodology, different canonical interpretation.

## 15. Missing / UNKNOWN Findings

There were no VWAP, trend, RS, RVOL, or gap unavailable observations in this
bounded sample. However:

- `SessionDataQualityStatus.EXPECTED_BAR_MISSING`: 270/370 (72.97%).
- OR30 was unavailable/forming/incomplete for 110/370 (29.73%).
- Stock-vs-sector RS was `UNKNOWN` for 194/370 (52.43%) because not every
  sector maps to a sector index.

Therefore OR30 and stock-vs-sector RS are poor mandatory v0 gates unless the
owner explicitly intends to wait or exclude unmapped sectors. Session data
quality needs policy attention before production emission.

## 16. Indirect Decision Provenance Impact

ID-6B.0's finding remains unchanged: current indirect Decision provenance is
insufficient. This baseline labels reconstructed ID evidence directly, but it
does not retrofit `DecisionEngine` provenance and does not claim that bound
Decisions have `NO_DECISIVE_PROVISIONAL_M5_DEPENDENCY`.

Production consequence: the future engine should mark finality
conservatively and prohibit irreversible rejection when indirect Decision
provenance is unknown.

## 17. Replay Limitations

This is settled historical market-time replay. It uses `as_of` cutoffs and
completed-candle semantics, but it cannot reconstruct provider-provisional
values observed live before settlement. ID-5B's `CASE_B_CONTENT_CHANGES`
therefore still matters for production semantics.

## 18. Forward-Outcome Feasibility

Existing candles can support a future ID-owned neutral MFE/MAE/time-to-target
harness. This milestone did not use EMR labels, EMR thresholds, EMR candidate
sets, EMR scoring, EMR final-test data, or the single production trade
outcome.

ID should create its own neutral evaluation harness later if the owner wants
to evaluate +1%/+1.5%, adverse excursion, and time-to-target behavior.

## 19. Performance / Runtime

- Primary replay runtime: 7.919 seconds.
- Determinism replay runtime: 8.107 seconds.
- Observation count: 370.
- No provider calls.
- No production DB writes.
- Research access pattern is bounded by sampled candidates and checkpoints;
  it does historical RVOL reads per observation, which is acceptable for the
  harness but not for a production engine.

The eventual ID-6B engine must remain O(1) per candidate by consuming already
produced artifacts.

## 20. Reusable Harness / Artifacts

Created reusable harness:

- `src/athena/data/id6b1_entry_qualification_baseline.py`

Created focused tests:

- `tests/data_layer/test_id6b1_entry_qualification_baseline.py`

Created research artifacts:

- `artifacts/research/id6b1/id6b1_summary.json`
- `artifacts/research/id6b1/id6b1_observations.jsonl`

Hashes:

- Stable analysis SHA-256:
  `7baf33e01df22d2acae000c44bcb7b0be0f2017d12248432e435eb986619b5fb`.
- Summary file SHA-256:
  `8d29837fe9be9a8ec6312342a2b5c51bccff17fa52cc1f6d6a05ee4791a34837`.
- Observation file SHA-256:
  `b0694987b06ae2932385a161119edd873aaf29fbb52e37857ec0591d76c08ebb`.

## 21. V0 Readiness-Policy Recommendation

Recommend owner approval for a conservative v0 categorical readiness policy,
with one condition:

```text
CANDIDATE_POLICY_MATCH:
  VWAP relation == ABOVE_VWAP
  AND trend_label == BULLISH
  AND (stock_vs_market RS == OUTPERFORMING
       OR stock_vs_sector RS == OUTPERFORMING
       OR RVOL relation == ABOVE_BASELINE)
```

Semantics if approved:

- May emit `QUALIFIED`.
- Evidence finality should be `LIVE_M5_PROVISIONAL` unless a later adapter can
  prove no decisive provisional-M5 dependency.
- Missing mandatory VWAP/trend should emit `UNKNOWN`.
- Negative VWAP/trend should emit reversible `NOT_YET`.
- RS/RVOL absence should not be bearish; if both are absent, emit `UNKNOWN`
  or `NOT_YET` per the owner-approved policy wording.
- OR15/OR30 remain contextual evidence, not mandatory.
- Gap remains contextual.
- `DISQUALIFIED_FOR_SESSION` remains unused.

Reason: the measured match rate is selective but not vanishingly rare, and
WATCH/TRADE behavior is similar enough to keep one methodology.

Condition: do not treat this as performance validated; require a larger replay
and live shadow evidence before promotion beyond advisory research output.

## 22. Confirmation-Policy Recommendation

Recommendation: do not emit `CONFIRMED_BY_POLICY` in the first engine version.

Reason: the candidate match flickered materially in the bounded sample. A
temporal persistence rule is plausible, but this sample is not enough to
freeze the number of checkpoints/bars required. A future confirmation policy
should be measured explicitly, likely using persistence across consecutive
completed observations, without equating confirmation to provider settlement.

## 23. Remaining Owner Decisions

1. Approve, revise, or reject the conservative v0 readiness policy in §21.
2. Decide how to handle `SessionDataQualityStatus.EXPECTED_BAR_MISSING` in
   production, because it appeared in 72.97% of sampled observations.
3. Confirm that OR15/OR30 stay contextual in the first engine version.
4. Confirm that `CONFIRMED_BY_POLICY` remains unused until a temporal
   persistence policy is measured and approved.
5. Authorize or defer ID-6B.2 pure engine implementation.

## 24. Final Recommendation

GO WITH CONDITIONS.

The evidence supports moving toward a small pure engine, but only after the
owner approves the v0 readiness policy and the SessionDataQuality handling.
Do not implement ID-6B.2 automatically from this report.

## Milestone Review Summary

**Name:** ID-6B.1 Entry Qualification Evidence Baseline & Policy Freeze

**Objective:** Measure existing ID evidence states across real historical
WATCH/TRADE candidates before freezing Entry Qualification methodology.

**Scope completed:** Recorded ID-6B.0 owner closure; built a reusable
read-only settled replay harness; reconstructed SessionContext,
IntradaySignalSet, VWAP, trend, OR15/OR30, RS, RVOL, Gap, and data-quality
state for 370 candidate-checkpoint observations; measured availability,
distributions, combinations, associations, checkpoint behavior, and
state-transition persistence.

**Files created:** `src/athena/data/id6b1_entry_qualification_baseline.py`,
`tests/data_layer/test_id6b1_entry_qualification_baseline.py`,
`docs/research/ID-6B.1-ENTRY-QUALIFICATION-EVIDENCE-BASELINE.md`.

**Files modified:** `docs/MILESTONES.md`,
`docs/ATHENA-ID-TRACK-HANDOFF.md`, `ATHENA_BRIEFING.md`,
`IMPLEMENTATION_SUMMARY.md`.

**Public APIs added:** None.

**Tests added:** 3 focused tests for baseline helpers/read-only guard.

**Test results:** `tests/data_layer/test_id6b1_entry_qualification_baseline.py`
passed; Ruff clean for the new harness/test; deterministic rerun produced the
same stable analysis SHA-256.

**Coverage summary:** Focused only; no production Entry Qualification engine
exists.

**Architecture compliance:** Preserves ADR-013, ATHENA-002, ADR-003, ADR-005,
ADR-012, and advisory-only/no-order boundaries. No scoring, Decision,
TradePlan, provider, DB, EMR, DarvaX, workflow, persistence, UI, or production
behavior changed.

**ADR compliance:** No new ADR required. Future provider, knowledge-time,
Decision, TradePlan, EMR, DarvaX, broker/order, persistence, or workflow
changes remain separately owner-gated.

**Risks discovered:** Session data quality is often not `SUFFICIENT` in
historical point-in-time replay; proposed candidate policy flickers; OR15/30
are highly associated; stock-vs-sector RS is often unavailable; indirect
Decision provenance remains insufficient.

**Technical debt introduced:** None in production behavior. The research
harness is bounded and reusable, but intentionally not optimized as a
production path.

**Suggested improvements:** Owner should decide the v0 readiness policy and
SessionDataQuality handling, then authorize ID-6B.2 as a pure engine only.

**Remaining work:** Owner policy review. Do not start ID-6B.2, ID-6C, ID-6D,
ID-6E, ID-7, EM-6, EMR, DarvaX, UI, provider, DB, workflow, persistence, or
production behavior until explicitly authorized.

**Commit message:**

```text
feat(data): add ID-6B.1 evidence baseline harness

- Record ID-6B.0 owner approval and ID-6B.1 evidence-baseline review status.
- Add a read-only settled historical replay harness for WATCH/TRADE candidate
  ID evidence distributions and deterministic policy-candidate measurement.
- Document measured availability, prevalence, association, transition, and
  policy-freeze findings without implementing Entry Qualification behavior.
```

**Ready for review:** Yes.
