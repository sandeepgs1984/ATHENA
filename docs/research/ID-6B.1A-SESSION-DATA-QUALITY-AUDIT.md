# ID-6B.1A Session Data Quality & Baseline Representativeness Audit

**Date:** 2026-09-02
**Track:** Intraday Intelligence
**Milestone:** ID-6B.1A - Session data quality root-cause and baseline representativeness audit
**Status:** Audit complete; ready for owner policy freeze review
**Recommendation:** GO WITH CONDITIONS

This milestone is diagnostic/research only. It does not implement the Entry
Qualification engine, does not add persistence, does not wire workflow, does
not add thresholds, does not create UI/API behavior, does not call
providers, and does not write `db/athena.db`. Production `SessionContext`,
`IntradaySignalSet`, `ScoringEngine`, `DecisionEngine`, `TradePlan`,
provider, workflow, and persistence code are unchanged.

## 1. Executive Summary

`SessionDataQualityStatus.EXPECTED_BAR_MISSING` fired for 270/370 (72.97%)
of ID-6B.1's observations despite VWAP/trend/RS/RVOL/Gap all being 100%
constructible. Root-caused to a genuine, real, systemic **M15 candle
off-grid condition**: in the real production database, M15 (15-minute)
candles are chronically off-grid (only the session's opening bar,
`09:15:00`, is reliably on-grid — one sampled instrument/session showed 1
on-grid row out of 27 total M15 rows for the day). `SessionContext`'s own
completion logic is **not defective** — it correctly and faithfully reports
that calendar-expected M15 bars are absent from the persisted store. The
underlying M15 data itself has never been subject to a settlement-repair
process analogous to `live_m5_settlement_repair.py`, which is hardcoded to
`Timeframe.M5` only.

Critically, **none of VWAP, RelativeStrengthContext, RelativeVolumeContext,
GapContext, or OpeningRangeEvidence (OR15/OR30) depend on M15 at all** —
confirmed by direct source inspection, not inference. Only the
trend/confluence label touches M15, and it uses a materially looser
retrieval contract (last-N-bars-by-limit, ID-5E-bounded, not the full
since-session-open due-set `SessionContext` requires) — which is why trend
was still constructible in all 270 "insufficient" rows. The blanket
`SessionDataQuality` gate answers a stricter, whole-session-completeness
question than any evidence family Entry Qualification's proposed v0 rule
actually consumes.

A broader, uncapped replay (7,144 observations vs. the original 370 — the
full population at the same five sessions and six checkpoints, not a
different sample) found every headline prevalence figure **broadly
stable** (within a few percentage points), confirming ID-6B.1's original
measurements were not an artifact of the 10-per-type cap. The one
exception is `TRADE`-specific figures, which remain genuinely
sample-sensitive because `TRADE` decisions are **temporally concentrated
on effectively one real trading day** (2026-08-26, plus one checkpoint on
2026-08-27) within this five-session window — a population-level
limitation the uncapped replay cannot fix, since it replays the same five
sessions.

Recommendation: **GO WITH CONDITIONS**. Do not use the blanket
`SessionDataQuality.SUFFICIENT` gate as an Entry Qualification precondition
(Policy Option C, artifact-owned availability). Document the M15 chronic
off-grid condition as a real, unresolved limitation and a candidate for a
future, separately-authorized M15 settlement-repair prerequisite milestone
(mirroring ID-5A) — not implemented here. Treat `TRADE`-specific prevalence
figures as provisional until a wider session window resolves the temporal
concentration.

## 2. ID-6B.1 Closure Recorded

`ID-6B.1 OWNER APPROVED / CLOSED — 2026-09-02`. The following owner
decisions from ID-6B.0/ID-6B.1 are preserved unchanged by this audit:

- WATCH and TRADE continue to use the same candidate Entry Qualification
  methodology unless later evidence justifies otherwise.
- OR15/OR30 remain contextual, not mandatory gates.
- `DISQUALIFIED_FOR_SESSION` remains unused in v0.
- `CONFIRMED_BY_POLICY` remains unused until confirmation methodology is
  separately measured and approved.
- No weighted/additive Entry Qualification score.
- The measured rule remains only `CANDIDATE_POLICY_MATCH` — **not**
  approved as production `QUALIFIED` methodology.

## 3. Exact `EXPECTED_BAR_MISSING` Semantics

From `src/athena/session/models.py`:

> Today's session has bars and expectations ARE computable (via
> `data/validation/calendar_expectations.py`), and at least one
> calendar-expected, already-due bar is missing.

`EXPECTED_BAR_MISSING` outranks `QUOTE_UNAVAILABLE` and is outranked only by
`SESSION_NOT_ACTIVE`/`TIMEFRAME_UNAVAILABLE`/`NO_CURRENT_SESSION_DATA`/
`INSUFFICIENT_HISTORY` in `SessionContextEngine._combine_quality`'s explicit
worst-first priority list — so if **either** the 5m or 15m timeframe has
even one missing due bar anywhere since session open, the **combined**
`SessionContext.data_quality` becomes `EXPECTED_BAR_MISSING`, regardless of
how much of the rest of the session's data is genuinely present.

## 4. Production Code Path

`SessionContextEngine._provenance` (`src/athena/session/engine.py`) calls
`_timeframe_quality` once per timeframe (5m, 15m):

```python
step = _TIMEFRAME_MINUTES[timeframe]
expected = expected_intraday_opens(calendar, session_date, step, tzinfo)
due = [ts for ts in expected if ts + timedelta(minutes=step) <= as_of]
present = {c.ts_open for c in today_candles}
missing = [ts for ts in due if ts not in present]
if missing:
    return EXPECTED_BAR_MISSING, f"{len(missing)}/{len(due)} ... missing ..."
```

`present` is an **exact timestamp-equality set** — a candle whose `ts_open`
does not land precisely on the canonical grid produced by
`expected_intraday_opens` can never satisfy `ts not in present`, no matter
how close it is in wall-clock time. This is intentional, existing,
ID-1/ID-2.1-era design (`athena.session.completed_candles`/canonical-slot
convention already used identically by ORB/RS/RVOL for M5) — not a defect
introduced or found in `SessionContext` itself.

`_combine_quality` then takes the worst of the two timeframe results.
`ind_stage`/`session_stage` in `owner_validation.py` feed `SessionContext`
real, session-bounded M5/M15 candle reads
(`get_candles(instrument_id, timeframe, session_day_start(as_of), as_of)`),
matching ID-6B.1's own harness retrieval exactly (verified in §6).

## 5. Candle Timestamp/Completion Convention

`is_candle_completed` (`athena.session.engine`): `ts_open + duration <=
as_of`. Confirmed unchanged and correctly applied everywhere in this audit
— no timestamp-rounding, flooring, or nearest-match logic exists anywhere
in the completion path.

## 6. Checkpoint-Boundary Audit

Verified by direct, independent recomputation (`id6b1a_session_quality_audit.py`,
`_timeframe_audit`, which re-derives `due`/`present`/`missing` from
`expected_intraday_opens` exactly as `_timeframe_quality` does, entirely
separately from `SessionContext`'s own internal call) against the real
`db/athena.db`, for the exact six ID-6B.1 checkpoints:

| Checkpoint | M5 due (measured) | M5 due (hand-computed) | M15 due (measured) | M15 due (hand-computed) |
|---|---|---|---|---|
| 09:30 | 3.0 | 3 | 1.0 | 1 |
| 09:45 | 6.0 | 6 | 2.0 | 2 |
| 10:00 | 9.0 | 9 | 3.0 | 3 |
| 11:00 | 21.0 | 21 | 7.0 | 7 |
| 13:00 | 45.0 | 45 | 15.0 | 15 |
| 14:30 | 63.0 | 63 | 21.0 | 21 |

Every measured `due` count exactly matches independent hand-calculation
(session open 09:15, `(as_of - 09:15) / step_minutes`). **No off-by-one or
exact-boundary defect exists in either the production `SessionContext`
logic or in ID-6B.1's own harness retrieval.** At `as_of=09:30`, the M5
interval opening at 09:25 is correctly due (09:25+5=09:30≤09:30); the
interval opening at 09:30 itself is correctly not yet due. ID-6B.1's
harness is correctly reconstructing the exact same boundary production
uses.

## 7. M5 Expected vs. Actual Breakdown

From the capped (370-observation) sample, averaged across candidates at
each checkpoint:

| Checkpoint | Avg M5 expected | Avg M5 present | Present/expected |
|---|---|---|---|
| 09:30 | 3.0 | 3.0 | 100.0% |
| 09:45 | 6.0 | 5.857 | 97.6% |
| 10:00 | 9.0 | 7.833 | 87.0% |
| 11:00 | 21.0 | 15.833 | 75.4% |
| 13:00 | 45.0 | 31.833 | 70.7% |
| 14:30 | 63.0 | 43.833 | 69.6% |

M5 presence **degrades gradually** as the session progresses but never
collapses — consistent with the already-known, already-documented
real-production M5 drift-onset pattern (settlement lag after
~09:35-09:40) this whole ID-5 sequence investigated and partially repaired
(ID-5A repairs settled dates; ID-5B classified live current-session
drift as `CASE_B_CONTENT_CHANGES`). This is expected, already-understood
behavior — not a new finding.

## 8. M15 Expected vs. Actual Breakdown

| Checkpoint | Avg M15 expected | Avg M15 present | Present/expected |
|---|---|---|---|
| 09:30 | 1.0 | 1.0 | 100.0% |
| 09:45 | 2.0 | 1.714 | 85.7% |
| 10:00 | 3.0 | 1.667 | 55.6% |
| 11:00 | 7.0 | 1.667 | 23.8% |
| 13:00 | 15.0 | 1.667 | 11.1% |
| 14:30 | 21.0 | 1.667 | 7.9% |

**M15 presence does not grow with the session at all** — it is
effectively frozen at ~1.667 bars present from 10:00 onward, regardless
of how many more M15 bars become due. This is qualitatively different
from M5's gradual degradation: M15 essentially stops accumulating
canonical, on-grid bars almost immediately after session open and never
recovers. Direct confirmation via raw SQL against the real database
(`NSE:AADHARHFC`, `NSE:RELIANCE`, 2026-08-26): M15 timestamps are
`09:15:00, 09:40:48, 09:55:48, 10:27:33, 10:42:33, 10:42:57, 10:57:57,
11:59:01, 12:14:01, 12:14:04, ...` — only `09:15:00` lands on the
canonical 15-minute grid (`:00/:15/:30/:45`, `:00` seconds); every
subsequent row is off-grid by anywhere from seconds to tens of minutes.
Of 27 total M15 rows persisted for that instrument/session, **exactly 1**
is on-grid. M5 for the same instrument/session is **100% on-grid**
(confirmed: `09:15:00, 09:20:00, 09:25:00, ...` exactly every 5 minutes),
consistent with ID-5A's own settlement repair having fixed M5 for settled
historical dates — a repair that was never extended to M15.

## 9. Root-Cause Classification of All 270 Affected Observations

| Root cause | Count | % of 270 |
|---|---|---|
| `M15_ONLY` (5m fully sufficient, 15m has missing due bars) | 180 | 66.67% |
| `BOTH_M5_AND_M15` | 80 | 29.63% |
| `M5_ONLY` (15m fully sufficient, 5m has missing due bars) | 10 | 3.70% |
| Unexplained (combine-logic surprise) | 0 | 0.00% |

**M15 involvement (`M15_ONLY` + `BOTH_M5_AND_M15`) accounts for 260/270
(96.30%) of all `EXPECTED_BAR_MISSING` observations.** Zero "unexplained"
cases — `SessionContextEngine._combine_quality`'s own logic is fully,
exactly consistent with an independent reconstruction; confirms no hidden
combine-stage defect.

Of the 180 `M15_ONLY` cases, only 40 (22.2%) have exactly one missing bar
that is the session's most-recently-due (terminal/still-settling) M15
slot — the remaining 140 (77.8%) have missing bars earlier in the session
too. This rules out "it's just the forming tail candle" as the
explanation; the condition is chronic, not an edge effect.

## 10. Breakdown by Checkpoint

| Checkpoint | `EXPECTED_BAR_MISSING` count (of 60-70) |
|---|---|
| 09:30 | 0 |
| 09:45 | 30 (20 `M15_ONLY`, 10 `M5_ONLY`) |
| 10:00 | 60 (40 `M15_ONLY`, 20 `BOTH`) |
| 11:00 | 60 (40 `M15_ONLY`, 20 `BOTH`) |
| 13:00 | 60 (40 `M15_ONLY`, 20 `BOTH`) |
| 14:30 | 60 (40 `M15_ONLY`, 20 `BOTH`) |

09:30 is always `SUFFICIENT` for M15 because exactly one M15 bar is due
(the genuinely on-grid opening bar). From 10:00 onward, the pattern is
stable at 40 `M15_ONLY` + 20 `BOTH` per checkpoint (of 60), i.e. the
population affected does not meaningfully change once the session is
past its first 45 minutes.

## 11. Breakdown by Session

| Session date | `EXPECTED_BAR_MISSING` root causes |
|---|---|
| 2026-08-26 | 100 × `M15_ONLY` |
| 2026-08-27 | 40 × `M15_ONLY` |
| 2026-08-28 | 40 × `M15_ONLY` |
| 2026-08-31 | 40 × `BOTH_M5_AND_M15`, 10 × `M5_ONLY` |
| 2026-09-01 | 40 × `BOTH_M5_AND_M15` |

The two most recent dates (2026-08-31, 2026-09-01 — both after ID-5B's
live capture) show `BOTH_M5_AND_M15` rather than pure `M15_ONLY`,
suggesting slightly worse M5 completeness on those specific dates than on
the three earlier, longer-settled dates. This is a real, minor,
descriptive observation, not independently investigated further here —
it does not change the overall conclusion (M15 dominates in every
session).

## 12. Breakdown by Decision Type

| Decision type | `EXPECTED_BAR_MISSING` root causes |
|---|---|
| TRADE | 50 × `M15_ONLY` (all from 2026-08-26) |
| WATCH | 80 × `BOTH_M5_AND_M15`, 130 × `M15_ONLY`, 10 × `M5_ONLY` |

Every affected TRADE observation traces to 2026-08-26 — consistent with
§17's finding that TRADE decisions in this five-session window are
almost entirely concentrated on that one day.

## 13. Evidence-Family Impact

Verified by direct source inspection (`Timeframe.` usage grep across each
engine), not inference:

| Evidence family | M5 dependency | M15 dependency | Affected by M15 off-grid? |
|---|---|---|---|
| VWAP | Yes (session-cumulative M5) | **None** | No |
| Trend/confluence (5m leg) | Yes | — | No |
| Trend/confluence (15m leg) | — | Yes, but via `list_candles_recent(limit=100, as_of=...)` (ID-5E-bounded last-N, not since-open due-set) | Materially reduced — SMA(5) only needs 5 present M15 bars from the last 100, not a gap-free since-open sequence |
| RelativeStrengthContext | Yes | **None** (confirmed: zero `Timeframe.` references outside M5 in `relative_strength_engine.py`) | No |
| RelativeVolumeContext | Yes | **None** (confirmed: `_BAR_STEP_MINUTES=5`, zero M15 references) | No |
| GapContext | **None** — D1 only | **None** | No |
| OpeningRangeEvidence (OR15/OR30) | Yes (canonical M5 slots) | **None** | No |

Only the 15m leg of the trend label touches M15 at all, and it does so
under a fundamentally looser contract than `SessionContext`'s own
completeness gate. This is why `IntradaySignalSet` construction and every
individual evidence family except the combined `SessionDataQuality` label
itself showed 100% (or near-100%, once uncapped — see §21) availability
despite the M15 off-grid condition.

## 14. Constructible-vs-Safe Analysis

"Constructible" (an artifact computed a value) and "safe for Entry
Qualification" (that value reflects genuinely sufficient underlying data)
are **not the same question**, and this audit finds no case where they
should be conflated to Entry Qualification's detriment:

- VWAP/RS/RVOL/Gap/OR15/OR30 are constructible **because they are
  genuinely M15-independent**, not because their own completeness checks
  are lenient. Their own contracts (`completed_candles`, exact canonical
  M5 slot matching for OR) are exactly as strict as `SessionContext`'s —
  they simply never ask an M15 question in the first place.
- The trend label's 15m leg is constructible under a genuinely looser
  contract (last-N-by-limit vs. since-open-due-set) — this is a real,
  deliberate design difference (ID-3.1 §5's own documented rationale:
  confluence's rolling SMA intentionally reads across session/day
  boundaries), not evidence being smuggled past a gate.
- OR15/OR30 being `COMPLETE` while `SessionDataQuality` reports
  `EXPECTED_BAR_MISSING` is **not contradictory** — they are answering
  disjoint questions (OR: "are this instrument's own canonical M5 slots
  for this specific 15/30-minute window present?"; `SessionDataQuality`:
  "are ALL M5-and-M15 bars due since session open present?"). OR's own
  contract never depended on M15 at all.

## 15. Quality-Impact Matrix

| Root cause | Affected evidence | Qualification consequence | Reason |
|---|---|---|---|
| M15 chronic off-grid (any earlier-in-session gap) | Combined `SessionDataQuality` label only | **Safe to evaluate normally** for VWAP/RS/RVOL/Gap/OR | Zero M5/M15 dependency confirmed by source for these families |
| M15 chronic off-grid | Trend label (15m leg) | Safe but evidence finality/provenance remains conservative | Constructible under a looser contract; do not silently upgrade its confidence |
| M5 partial drift (later checkpoints, gradual) | VWAP/RS/RVOL/OR (cumulative-since-open families) | Already-handled by each engine's own honest-unavailable/partial-window semantics (ID-1 through ID-5D.1) | Not a new finding; existing contracts already degrade gracefully |
| M15 near-total absence beyond the opening bar | The blanket `SessionDataQuality.SUFFICIENT` gate itself | **NOT_YET** as a blanket precondition; artifact-specific exclusion preferred | Blanket gate answers a stricter question than any consumed evidence family actually needs |
| Underlying M15 data has no settlement-repair mechanism | Any future artifact that might legitimately need since-open M15 completeness | Production defect requiring prerequisite fix — **not fixed here** | `live_m5_settlement_repair.py` is hardcoded `Timeframe.M5`; no M15 equivalent exists anywhere in the repository |

## 16. Original Sampling Design

ID-6B.1: 5 consecutive sessions (2026-08-26, 27, 28, 31, 09-01), 6
checkpoints, deterministic cap of 10 candidates per Decision type per
session/checkpoint, ordered `decision_type, instrument_id` (alphabetical
within type) before capping — i.e. the cap deterministically retains the
alphabetically-first up-to-10 instruments per type per checkpoint, not a
random or outcome-weighted sample.

## 17. Candidate Population Before Cap

Measured directly via the same production `decisions` table query, without
the Python-side per-type cap:

- **Total population: 7,144** candidate-checkpoint pairs (5,668 WATCH +
  1,476 TRADE) across the same 5 sessions × 6 checkpoints.
- ID-6B.1's capped sample (370) retained **5.18%** of the total available
  population.
- **TRADE population is severely temporally concentrated**: 218-227 TRADE
  candidates per checkpoint on 2026-08-26 (all 6 checkpoints), 197 at the
  single 2026-08-27 09:45 checkpoint, and **zero TRADE candidates at
  every other session/checkpoint combination** (2026-08-27's other 5
  checkpoints, all of 2026-08-28, 2026-08-31, 2026-09-01). All 70 of
  ID-6B.1's original TRADE observations trace to these same two dates —
  confirmed exactly by §12's root-cause breakdown, where every M15-related
  TRADE failure is dated 2026-08-26.
- Instrument concentration in the capped sample: top-10 instruments
  appear 13-22 times each (of a possible 30 session/checkpoint slots) —
  meaningful but not extreme concentration, consistent with the
  deterministic alphabetical-cap ordering rather than genuine population
  skew.

**Population representativeness is NOT claimed for TRADE** without a
wider session window containing more genuine TRADE-decision days. WATCH's
much larger and more evenly-distributed population (5,668 across all
5×6=30 session/checkpoint cells) supports the original capped sample's
own conclusions reasonably well (confirmed by §21's stability comparison).

## 18. Cap/Concentration Analysis

See §17. The 10-per-type cap itself (as opposed to TRADE's temporal
concentration) is shown by §21 to have a modest, generally
non-material effect on headline prevalence figures — the broader,
uncapped replay changes most figures by only a few percentage points.

## 19. Broader/Uncapped Replay Design

Chose **Option A** (uncap the same five sessions) per the milestone's own
stated preference: reran ID-6B.1's own unmodified `run_baseline()`
(`src/athena/data/id6b1_entry_qualification_baseline.py`, no code changes)
with `per_type=1000` (safely above the real maximum of 227 candidates per
type per checkpoint) against the same five sessions and six checkpoints,
producing every eligible WATCH/TRADE candidate rather than a capped
sample. Same read-only safety (`mode=ro` + `PRAGMA query_only=ON`), same
production engines, same deterministic-digest mechanism.

## 20. Broader Replay Observation Count

**7,144 observations** (5,668 WATCH + 1,476 TRADE), 381 distinct
instruments, 5 distinct sessions — exactly matching the population
measured independently in §17. Runtime: 194.591 seconds (vs. 7.919
seconds for the original 370-observation capped run) — linear-ish scaling
with observation count, no read-only-safety or determinism concern at
this larger scale. Deterministic analysis SHA-256:
`bee4626fb0d418db2643bce0d286a6500b080f1bc21e11fd124cfa1fd7014491`.

## 21. Original-vs-Broader Stability Comparison

| Metric | Capped (n=370) | Uncapped (n=7,144) | Δ (pp) | Classification |
|---|---|---|---|---|
| `ABOVE_VWAP` | 36.22% | 39.84% | +3.62 | Broadly stable |
| `BULLISH` trend | 35.95% | 36.11% | +0.16 | Broadly stable |
| RS stock-vs-market `OUTPERFORMING` | 39.73% | 46.67% | +6.94 | Moderately sample-sensitive |
| RVOL `ABOVE_BASELINE` | 25.41% | 26.51% | +1.10 | Broadly stable |
| VWAP + trend (`vwap_and_trend`) | 21.89% | 24.50% | +2.61 | Broadly stable |
| `CANDIDATE_POLICY_MATCH` (overall) | 17.57% | 20.53% | +2.96 | Broadly stable |
| WATCH match rate | 17.00% | 18.53% | +1.53 | Broadly stable |
| TRADE match rate | 20.00% | 28.25% | +8.25 | Moderately sample-sensitive (temporal concentration, §17) |
| True-then-later-false (flicker) | 37.84% (n=74 groups) | 46.43% (n=1,273 groups) | +8.59 | Moderately sample-sensitive — and directionally **worse** with more data |
| OR15/OR30 phi | 0.7439 | 0.7048 | -0.0391 | Broadly stable |
| VWAP/trend phi | 0.3848 | 0.4299 | +0.0451 | Broadly stable |
| RS/RVOL phi | 0.1211 | 0.1601 | +0.0390 | Broadly stable |
| `EXPECTED_BAR_MISSING` | 72.97% | 71.96% | -1.01 | Broadly stable — confirms the M15 finding is not a capped-sample artifact |

**Criterion used (descriptive, not a statistical promotion threshold, per
explicit instruction):** "broadly stable" = single-digit percentage-point
shift with no directional reversal; "moderately sample-sensitive" = larger
shift, generally traceable to a specific, already-identified population
concentration (TRADE's temporal concentration); "materially unstable"
(not observed for any measured figure) would mean a shift large enough to
change which candidate-policy conclusion the figure would support.

The broader replay also surfaced 30 observations (0.42%) with
`TIMEFRAME_UNAVAILABLE`/`VWAP_UNAVAILABLE`/RS-`UNKNOWN`/RVOL-`UNKNOWN` —
candidates with genuinely no M5 candle history at all in the wider
population. A minor, expected edge case (consistent with occasional
newly-added or thinly-covered instruments elsewhere in this project's
history), not separately investigated further here.

## 22. WATCH-vs-TRADE Stability

WATCH is stable (17.00% → 18.53%, +1.53pp) across both samples — the
much larger, evenly-distributed WATCH population (5,668 across all 30
session/checkpoint cells) supports this. TRADE moved more (20.00% →
28.25%, +8.25pp), but this reflects TRADE's underlying temporal
concentration (§17), not a flaw in the uncapped methodology — uncapping
the same five sessions cannot manufacture TRADE decisions on the three
sessions where none exist. **TRADE-specific prevalence conclusions
should be treated as provisional** until measured across a wider window
containing more genuine TRADE-decision days.

## 23. Candidate-Policy Stability

`CANDIDATE_POLICY_MATCH` (the illustrative
`VWAP-above AND bullish-trend AND (RS-outperform OR RVOL-above)` rule)
moved from 17.57% to 20.53% (+2.96pp) — broadly stable, and the rule
remains genuinely selective at both sample sizes (roughly 1-in-5 to
1-in-6 observations match), not a near-universal or near-never rule
either way.

## 24. Flicker Stability

Flicker (`true_then_later_false`) moved from 37.84% (n=74 multi-checkpoint
groups) to 46.43% (n=1,273 groups) — a materially larger, more reliable
sample confirming (and slightly worsening) ID-6B.1's own original
finding. This reinforces, does not weaken, ID-6B.1's own recommendation
to defer `CONFIRMED_BY_POLICY` and any temporal-persistence rule.

## 25. Replay Limitations

Unchanged from ID-6B.1: settled historical market-time replay only (ID-5E/
5F/5G point-in-time contracts), not live knowledge-time reconstruction.
Indirect Decision provenance remains insufficient. This audit adds no new
outcome-optimization capability — see §26.

## 26. Recommended Production Quality Policy

**Recommendation: Option C — Artifact-owned availability**, with an
explicit, documented M15 caveat (not a pure "C" without qualification):

Entry Qualification should consume each evidence family's own explicit
availability/quality signal (VWAP `available`, RS `stock_available`/
`sector_available`/`market_available`, RVOL `available`, Gap `available`,
OR `status`) directly, rather than gating on the blanket
`SessionContext.data_quality` label. This is safe because §13/§14
establish, by source inspection, that none of these families' own
availability semantics are weakened by M15's chronic off-grid condition —
they simply never depend on M15.

The trend label's own 15m leg should remain visible as `None`/unavailable
in its own existing sub-field (`TimeframeTrendEvidence.bullish=None`)
exactly as designed — no change needed; a future Entry Qualification
engine can already see this distinction if it consumes the trend
context's own sub-fields rather than only the aggregate label.

Do NOT choose Option A (hard UNKNOWN gate on any `EXPECTED_BAR_MISSING`):
measured evidence shows this would make ~73% of otherwise-fully-evidenced
observations unreadiness-evaluable for a condition (M15 completeness)
that materially affects none of the artifacts the proposed v0 policy
actually uses.

Do NOT choose Option D as the full disposition: `SessionContext` itself
is not defective. However, flag the underlying **M15 data gap** (§8, §15)
as a genuine prerequisite candidate: a future, separately-owner-authorized
milestone analogous to ID-5A (M15 settlement repair) would be needed
before any future evidence family that genuinely depends on M15
completeness could be trusted. This is explicitly not authorized or
scoped here.

## 27. Re-Evaluated v0 Readiness Policy

The illustrative combination

```text
VWAP == ABOVE_VWAP
AND trend == BULLISH
AND (
    stock-vs-market RS == OUTPERFORMING
    OR stock-vs-sector RS == OUTPERFORMING
    OR RVOL == ABOVE_BASELINE
)
```

remains selective and stable across both the capped (17.57%) and uncapped
(20.53%) samples. Recommendation: **MORE EVIDENCE REQUIRED before
FREEZE**, specifically:

1. Owner ratification of the Option C artifact-owned-availability policy
   (§26) — this changes which observations are even eligible for
   evaluation, which could shift the rule's own measured prevalence once
   applied.
2. A wider TRADE-representative session window, given §17/§22's finding
   that TRADE evidence in this window is concentrated on effectively one
   day.

This is **not called performance-validated**. If frozen after the above,
it remains a v0 advisory readiness methodology awaiting later outcome/
replay/shadow validation (§25).

## 28. Confirmation Status

`CONFIRMED_BY_POLICY` remains deferred, unchanged from ID-6B.1. §24's
larger-sample flicker measurement (46.43%, up from 37.84%) reinforces
this: no arbitrary two-bar/two-checkpoint/N-minute persistence rule is
introduced here.

## 29. Terminal-State Status

`DISQUALIFIED_FOR_SESSION` remains off in v0, unchanged. All negative
readiness behavior in a first engine remains reversible unless lifecycle
semantics independently produce `OUT_OF_SCOPE`/`EXPIRED` (ID-6A contract,
unchanged by this audit).

## 30. Risks / Open Questions

- The M15 settlement-repair gap (§8, §15, §26) is real, unrepaired, and
  its true production-cadence severity (live, not just historical) is not
  measured here — this audit is a settled historical replay, not a live
  canary. A future milestone would need its own live-session evidence,
  mirroring ID-5B's own discipline, before claiming any M15 fix works
  live.
- TRADE's temporal concentration (§17) means this audit cannot yet
  confirm TRADE/WATCH methodology parity holds under genuinely diverse
  TRADE conditions — only that it holds for the TRADE decisions that
  happened to occur in this window.
- The Option C policy shift itself has not been applied and re-measured
  against the sample — §27's "more evidence required" reflects that this
  audit evaluates root cause and representativeness, not the downstream
  effect of adopting Option C.
- Indirect Decision provenance and forward-outcome feasibility remain
  exactly as limited as ID-6B.1 already reported (§25) — not solved or
  worsened by this audit.

## 31. GO / GO WITH CONDITIONS / PREREQUISITE REQUIRED / MORE EVIDENCE REQUIRED

**GO WITH CONDITIONS.** Session data quality root cause is fully
understood and evidenced (§3-§15); it is a real M15 data limitation, not
a `SessionContext` code defect, and it does not compromise the evidence
families the proposed v0 policy actually consumes. The baseline's
headline prevalence figures are broadly stable under a 19x larger,
uncapped sample (§21), with the single, well-understood exception of
TRADE-specific figures (§17, §22). Conditions: owner ratification of the
Option C quality policy (§26), and treating TRADE-specific findings as
provisional pending a wider session window, before the v0 policy itself
is frozen (§27).

## 32. Suggested Next Slice

Not authorized here. If the owner ratifies Option C, the natural next
slice would be re-measuring the same baseline under the Option C
availability policy (still read-only, still no engine) before any ID-6B.2
pure-engine implementation is authorized. A separate, explicitly
owner-authorized M15 settlement-repair investigation (mirroring ID-5A)
is a candidate for later, independent scheduling — not proposed as the
immediate next step.
