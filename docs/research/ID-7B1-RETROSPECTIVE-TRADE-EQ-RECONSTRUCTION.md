# ID-7B.1 — Retrospective TRADE+EQ Reconstruction & Entry/Risk Methodology Evidence

**Status: RESEARCH COMPLETE — target cohort reconstructed sufficient;
evidence-blocker that limited ID-7B removed. Read-only throughout: zero
writes to any canonical table, zero schema, zero `src/` modification,
zero provider/network calls. Companion to
`docs/research/ID-7B-ENTRY-RISK-METHODOLOGY.md`, which this milestone
extends with real evidence, not a replacement for it.**

## 1. Purpose and critical terminology

ID-7B found zero real historical `(Decision.decision_type=TRADE,
EntryQualification.state=QUALIFIED)` episodes, because
`entry_qualifications` persistence only began 2026-09-03 while all real
`TRADE` decisions occurred 2026-07-31 through 2026-08-27. ATHENA already
has (a) a frozen, deterministic EQ v0 methodology
(`EntryQualificationEngine`) and (b) real historical M5/M15/D1 market
data covering that entire window. This milestone asks: can the frozen
EQ v0 engine be run **retrospectively**, bounded strictly to
market-time evidence available at each historical `TRADE` decision's own
evaluation checkpoint, to produce a real, sizeable research cohort —
without touching production?

**Terminology, enforced everywhere in this document and in every
generated artifact**: reconstructed rows are never "production EQ,"
never "persisted EQ," never "observed production QUALIFIED." They did
not exist operationally at that historical time. The correct terms are
`RETROSPECTIVE_EQ_REPLAY` and `REPLAYED_QUALIFIED` (or the analogous
`REPLAYED_NOT_YET`/`REPLAYED_UNKNOWN`/`REPLAYED_EXPIRED`). This document
answers: *what would the CURRENT frozen EQ v0 methodology conclude using
historical market data bounded at that checkpoint?* It does **not**
claim to reconstruct what the production system literally knew, in real
time, on that historical date (EQ did not exist then) — this is
market-time replay, not knowledge-time reconstruction, exactly the
limitation ADR-013 already documents and this milestone preserves
unchanged (§5).

## 2. Read-only safety proof

All canonical-database access used `ReadOnlyStore`
(`src/athena/data/id6b1_entry_qualification_baseline.py`, `mode=ro` +
`PRAGMA query_only=ON`) — an existing, unmodified, already
owner-approved (ID-6E) class. A live write-rejection assertion
(`DELETE FROM decisions WHERE 1=0`, expected to raise
`sqlite3.OperationalError`) was executed and passed. `git status --short`
at repo root is clean throughout — zero files under `src/`, `config/`,
or any tracked path were created, modified, or touched. All research
artifacts (working scripts, an intermediate SQLite results cache,
aggregated JSON summaries) live outside the tracked repository tree,
under the session scratchpad. No `src/` file was modified — only
imported from (`ReadOnlyStore`, `IntradayAnalyticsEngine`,
`OpeningRangeEngine`, `RelativeStrengthEngine`, `RelativeVolumeEngine`,
`GapEngine`, `EntryQualificationEngine`, `EntryQualificationPolicy`,
`resolve_evidence_finality`, `SessionContextEngine`, `IndicatorEngine`,
`CalendarEngine`, config loaders — all real production classes, called
read-only, never edited).

## 3. Reconstruction method — reuse, not reimplementation

The reconstruction pipeline reuses, almost verbatim, the inner
per-candidate logic already inside `src/athena/data/id6e_replay_shadow_validation.py`'s
`run_replay()` (lines 150-273) — an existing, ID-6E owner-approved
historical replay harness. That harness sweeps FIXED wall-clock
checkpoints; this milestone instead drives the identical reconstruction
block using each REAL historical `TRADE` decision's own `ts` as the
`as_of` checkpoint. For each: `SessionContextEngine.assess(...)` builds
`SessionContext`; completed M5/M15 candles feed `IndicatorEngine`
(VWAP) and a `ConfluenceInputs` (for trend); `OpeningRangeEngine`,
`RelativeStrengthEngine` (fed real NIFTY 50 + sector-index M5 candles),
`GapEngine`, and `RelativeVolumeEngine` build the remaining evidence;
`IntradayAnalyticsEngine.assess(...)` assembles the real
`IntradaySignalSet`; `resolve_evidence_finality(decision, session_context)`
and the real, unmodified `EntryQualificationEngine.evaluate(...)`
produce the final `RETROSPECTIVE_EQ_REPLAY` result. Nothing about the
v0 formula was re-derived or approximated.

## 4. Historical TRADE inventory & feasibility

96,985 real `TRADE` decisions exist, 2026-07-31 through 2026-08-27, 381
distinct instruments, spanning only **20 distinct session dates**. A
300-decision stride-sampled feasibility pass (evenly spread across the
full window) reconstructed successfully **300/300 (100%)**, ~0.0265s/
decision — establishing the pipeline works and scales. Required
benchmark data (`NSE:NIFTY 50` M5 from 2026-07-24; sector indices from
2026-07-28) both predate the TRADE window, removing the main plausible
feasibility risk before the full run.

## 5. Market-time replay limitation (preserved, not resolved)

Unchanged from ADR-013 and ID-6E: this is settled historical
**market-time** replay — every input is bounded to completed candles
at-or-before the checkpoint `as_of`, exactly as `is_candle_completed`
already enforces in production. It is **not** full bitemporal
knowledge-time replay: it says nothing about what the (nonexistent, at
that date) production EQ path would have literally known in real time,
and cannot correct for any provider-settlement differences a
now-vs-then comparison might carry. Every reconstructed row is a
statement about the frozen methodology's behavior against the data
representation the database holds *today*, not a historical fact about
2026-08's live system state.

## 6. Config/methodology-drift audit

Joining `decisions`→`runs` for every `TRADE` row: all 96,985 share the
identical `software_version=0.1.0`, `blueprint_version=ATHENA-002 v1.1`,
`strategy_profile=intraday-momentum`, `strategy_profile_version=1`. Only
`config_snapshot_id` varies — an **operational trigger-path** label, not
a methodology version: `cfg-host-ops` (55,043, the normal scheduled
cycle), `cfg-fast-revalidation` (37,233, the FAST tier's own scoped,
~10-minute-cadence universe), `cfg-full-validation` (4,216, owner-
triggered "Validate All"), `cfg-symbol-validate` (489), `cfg-cli` (4).
**No methodology/blueprint stratification is required** — the
population is structurally homogeneous at the methodology level. (A
real, interesting *qualified-rate* difference by trigger path is
reported descriptively in §16 — not a methodology-drift issue.)

## 7. Decision-churn / episode construction

96,985 raw rows are not 96,985 independent opportunities: they collapse
to **4,968 distinct (instrument, session_date) groups** (median ~11
repeated `TRADE` decisions per group, mean 14.64, max 60 —
`NSE:PAYTM` on 2026-08-10). A **zero-invented-parameter** episode
boundary was used — group consecutive-in-time `TRADE` decisions for the
same instrument+session into one episode; an episode boundary occurs
only when a non-`TRADE` decision for that instrument intervenes (any
`decision_type` change breaks the run) or the session date changes — no
arbitrary time-gap threshold anywhere. This produced **6,624 episodes**
(independently re-derived twice — a fast standalone cross-check and the
full Stage-2 pipeline's own derivation both agree exactly on 6,624, with
an internal sum-of-lengths check confirming all 96,985 rows are
accounted for). Median episode length 11, mean 14.64, max 60; only
15.72% (1,041) are single-cycle (no churn at all).

**Both cohorts, as required:**
- **OBSERVATION cohort** = the full 96,985 raw rows (not exhaustively
  reconstructed in this milestone — see §17).
- **EPISODE cohort (primary, used throughout §§8-16)** = 6,624 episodes,
  each represented by its **first checkpoint** — the moment an
  instrument first became `TRADE`-classified that session, the natural
  entry-timing-relevant instant, and the choice that avoids
  over-weighting heavily-churned symbols.

## 8. Full-scale reconstruction result (episode cohort)

All 6,624 episode-first-checkpoints reconstructed: **6,624/6,624
(100%), zero failures, zero exceptions of any kind.** Runtime 62.5s.

**`RETROSPECTIVE_EQ_REPLAY` state distribution:**

| State | Count | % |
|---|---|---|
| `NOT_YET` | 4,407 | 66.53% |
| `EXPIRED` | 1,106 | 16.70% |
| `REPLAYED_QUALIFIED` | 783 | 11.82% |
| `UNKNOWN` | 328 | 4.95% |

No `DISQUALIFIED_FOR_SESSION` or `OUT_OF_SCOPE` observed (consistent —
every input row is already a real `TRADE` decision during `REGULAR`
session hours by construction).

## 9. LONG vs SHORT replay distribution — and a sharper finding than ID-7B's own

**All 783 `REPLAYED_QUALIFIED` episodes are `LONG`** — consistent with
`VwapRelation.ABOVE_VWAP` (783/783) and `IntradayTrendLabel.BULLISH`
(783/783), an exact internal-consistency check against EQ v0's own
formula. But the sharper finding: **zero `SHORT` decisions exist
anywhere in `db/athena.db`, of ANY `decision_type`, not only `TRADE`.**
Direct query across the full `decisions` table (233,418 rows, all
types) found exactly two `direction` values present: `LONG` (96,985)
and `NONE` (136,433, i.e. `WATCH`/`NO_TRADE`, which carry no
directional stance at all). **`SHORT` is not merely rare or
disqualified by EQ — it has never occurred in this dataset at any
layer.** This sharpens (not contradicts) ID-7B's original finding: the
asymmetry is not proven to be EQ's formula alone rejecting SHORT
candidates — there is no SHORT candidate population for EQ to be tested
against in the first place. The root cause, if one exists, sits at
least one layer further upstream (Decision/scoring/`intraday-momentum`
strategy profile), a genuinely separate, wider-scoped question than ID-6
alone. **Not investigated further here** — this milestone does not
modify ID-6 or the scoring/strategy layer (§20 restates this boundary).

## 10. Session-grouped chronological split feasibility

Only **20 distinct session dates** carry any `TRADE` decision. A
chronological discovery/validation split by session group is
*technically executable* (e.g. a majority of sessions for discovery, a
minority held out for validation, never splitting individual
observations within a session) but would produce a genuinely small
validation set given the total session count — this milestone does
**not** claim a statistically robust split exists or execute one (no
threshold-fitting occurs in this milestone at all, per §21/§27's
scope). A future calibration milestone should treat this explicitly —
likely favoring a leave-some-sessions-out or cross-validation-style
approach over a single fixed split, given the small session count — a
recommendation only, not decided here.

## 11. TRADE + REPLAYED_QUALIFIED cohort size

**783 episodes** (11.82% of the 6,624-episode cohort). This is the
target research population for §§12-16 below.

## 12. Mandatory evidence availability on the target cohort (real, not general-population proxy)

| Evidence | Availability |
|---|---|
| VWAP | 783/783 (100%) |
| VWAP `deviation_pct` | 783/783 (100%) |
| M5 trend leg | 783/783 (100%) |
| M15 trend leg | 783/783 (100%) |
| RelativeStrength | 783/783 (100%) |
| RelativeVolume | 783/783 (100%) |
| D1 ATR | 783/783 (100%) |
| GapContext | 783/783 (100%) |
| OR15 `COMPLETE` | 778/783 (99.36%) |
| OR30 `COMPLETE` | 714/783 (91.19%) |

Both OR figures are notably **higher** than PS-P9B's general-population
figures (93.25%/68.54%) — consistent with `QUALIFIED` checkpoints
tending to occur later in the session, after the opening-range window
has had more time to complete. This is exactly why the milestone
required target-population evidence rather than reusing the earlier
general-population proxy.

## 13. Entry-anchor candidates — comparison only, none frozen

Three candidates evaluated (a fourth, "recent M5 structural
breakout/trigger," was explicitly **not evaluated** — no predeclared
lookback-window authority exists anywhere in the repo; inventing one
here would violate the milestone's own prohibition):

| Anchor | Availability | Distance median (%) | Distance median (ATR-norm.) |
|---|---|---|---|
| `CANDIDATE_ENTRY_ANCHOR_VWAP` | 94.38% | 0.460 | 0.162 |
| `CANDIDATE_ENTRY_ANCHOR_QUALIFYING_M5_CLOSE` | 94.38% | 0.0 (by construction) | 0.0 |
| `CANDIDATE_ENTRY_ANCHOR_OR15` | 93.74% | 0.122 | 0.053 |

The M5-close anchor is trivially zero-distance (it *is* the checkpoint
price) — useful as the baseline for forward price-move measurement
(§15), not as an "extension" signal on its own. Price sits, on median,
closer to the OR15 high than to VWAP at the qualifying checkpoint.

**Forward evolution of anchor distance** (median, %):

| Anchor | +5m | +10m | +15m |
|---|---|---|---|
| VWAP | 0.502 | 0.462 | 0.470 |
| OR15 | 0.183 | 0.133 | 0.129 |
| Qualifying M5 close | 0.015 | 0.0 | 0.0 |

Distances are broadly stable across the 15-minute forward window rather
than monotonically widening — consistent with §15's freshness finding
that the typical case is not materially stale.

## 14. Entry-extension distributions (full percentile detail)

VWAP-anchor distance (%) at checkpoint: p25 0.227 / median 0.460 / p75
0.795 / p90 1.200 / p95 1.496 / max 2.731. OR15-anchor distance (%): p25
−0.259 / median 0.122 / p75 0.641 / p90 1.375 / p95 1.974 / max 6.496 (a
materially fatter tail than VWAP's). ATR-normalized versions available
in the underlying data cache for both. No threshold selected — this is
the exact empirical basis a future calibration milestone should use for
choosing an extension/chase cutoff, not a recommendation of one.

## 15. Freshness — target-cohort specific (supersedes ID-7B's general-population proxy)

| Horizon | VWAP-side still above | Trend still BULLISH | Move % (median / p90 / p95) |
|---|---|---|---|
| +5m | 90.53% | 81.73% | 0.015 / 0.451 / 0.748 |
| +10m | 87.11% | 72.98% | 0.0 / 0.492 / 0.770 |
| +15m | 83.36% | 63.55% | 0.0 / 0.575 / 0.907 |

**Cross-validation of ID-7B's own general-population proxy**: that
earlier estimate (88.32% VWAP-side persistence over a ~10-minute gap,
138,454 general-market samples) is remarkably close to this
target-cohort's real +10m figure (87.11%) — the general-population
proxy turns out to have been a good approximation for VWAP-side
persistence specifically. **New, more granular finding the proxy could
not provide**: trend persistence degrades meaningfully faster than
VWAP-side persistence (72.98% vs 87.11% at +10m) — a genuinely new
nuance for any future freshness/extension gate design: trend-reversal
risk over the canonical-cycle timescale is real and larger than
VWAP-side flip risk. Move-size distributions closely match ID-7B's
general-population proxy in shape (small median, real but bounded
tail).

**Reassessment**: `CONDITIONAL_ON_EVIDENCE_AGE` (ID-7B's classification)
is **confirmed, not overturned**, by target-cohort evidence, with one
refinement: the freshness gate's evidence-age term should weight trend
persistence, not only VWAP-side persistence, since trend degrades
faster.

## 16. Outcome labels (descriptive only; frozen horizon: same-session, checkpoint→session close; no ML, no horizon search)

| Label | Value |
|---|---|
| MFE (median / p90 / p95) | 0.434% / 1.986% / 2.741% |
| MAE (median / p90 / p95) | −0.474% / 0.105% / 0.251% |
| T1 (+1%) hit rate | 23.88% (187/783) |
| T1 time-to-hit (median / p90) | 59.6 min / 217.8 min |
| T2 (+1.5%) hit rate | 14.81% (116/783) |
| T2 time-to-hit (median / p90) | 108.0 min / 266.0 min |
| MAE before T1 (median / p90, T1-hitters only) | 0.0% / 0.948% |
| MAE before T2 (median / p90, T2-hitters only) | 0.013% / 0.820% |

Roughly one in four `REPLAYED_QUALIFIED` LONG episodes reaches the
+1% goal band within the same session; roughly one in seven reaches
+1.5%. The large majority (76%) do not reach even T1 within the
horizon — a real, sobering, honestly-reported base rate, not evidence
either for or against the methodology's eventual usefulness on its own
(no comparison population — e.g. non-QUALIFIED TRADE episodes — was
computed in this milestone; recorded as a natural next question, §22).

## 17. Session-boundary / outcome-leakage safeguards

Zero cross-session violations across all 783 rows checked. Forward
windows were computed via a direct SQL filter
(`substr(ts_open,1,10)=session_date AND ts_open>checkpoint_ts`), never a
row-count `LIMIT` — so a forward window can never silently extend into
the next session regardless of how close to session close a checkpoint
falls. Every entry-anchor/extension/invalidation input used only
completed candles at-or-before the checkpoint; every forward label used
only data strictly after the checkpoint, same session.

## 18. Invalidation candidates — independent evaluation, no precedence chosen

| Candidate | Availability | Stop-hit rate | Stop-before-T1 | Stop-before-T2 | Time-to-hit (median) |
|---|---|---|---|---|---|
| VWAP-loss | 94.38% | 66.98% | 87.68% | 94.55% | 40.3 min |
| OR15 boundary | 93.74% | 63.76% | 96.79% | 99.36% | **9.2 min** |
| D1 ATR (1×, descriptive only) | 94.38% | 1.76% | 69.23% | 100.0% | 261.0 min |

OR15-boundary invalidation triggers markedly faster (median 9.2 min)
than VWAP-loss (40.3 min) and is hit before T1 nearly every time it
fires (96.79%) — consistent with PS-P9B's own caution that raw OR
boundary crossings are frequent/noisy, not a slow, deliberate structural
break. The D1-ATR fallback (explicitly a descriptive 1×ATR reference,
**not** a proposed stop multiplier) is, as intended for a fallback,
rarely triggered at all (1.76%) and slow when it is.
`recent_completed_M5_extremum` was **not evaluated** — no predeclared
lookback authority exists (same finding as §13).

## 19. Reward/risk descriptive evidence — a genuine methodological finding: degenerate pairs

Every non-degenerate entry-anchor × invalidation-candidate pairing was
computed (risk distance, reward-to-T1/T2 %, RR to T1/T2). Two pairings
are **structurally degenerate** and must never be used together: pairing
the VWAP anchor with VWAP-loss invalidation, or the OR15 anchor with
OR15-boundary invalidation, produces a **zero risk distance by
construction** (both are literally the same reference level) — RR is
undefined (0% availability) for both. This is a real, useful discovery
for any future engine design: **the entry anchor and invalidation
candidate must be drawn from independent reference levels.**

Representative non-degenerate pairs (RR to T1, median): `M5_CLOSE vs
VWAP_LOSS` 2.19; `M5_CLOSE vs OR15_BOUNDARY` 1.74; `VWAP vs
ATR_FALLBACK` 0.65; `OR15 vs ATR_FALLBACK` 0.42. (Full distributions —
p25/p75/p90/p95, plus RR-to-T2 and risk-distance-% — recorded in the
underlying data cache for every pair; not all reproduced here for
brevity.) No minimum-RR gate is proposed — purely descriptive, exactly
as authorized.

## 20. RS / RVOL / Gap — descriptive splits only, no fitting, no gate

| Split | Lowest group T1 hit rate | Highest group T1 hit rate |
|---|---|---|
| RS `stock_vs_market_pct` quartile | Q1: 16.33% | Q4: 33.16% |
| RVOL `rvol_ratio` quartile | Q2: 17.86% | Q4: 31.12% |
| Gap direction | GAP_UP: 23.35% | FLAT: 26.87% |
| Gap % quartile | Q3: 21.65% | Q2: 25.38% |

RS and RVOL magnitude both show a visible, monotonic-ish directional
pattern in this purely descriptive cross-tab (higher relative strength
or relative volume associated with a higher T1 hit rate) — a real
signal worth flagging as a candidate for promotion from context-only to
a future methodology input, **not** decided or fitted here. Gap shows
no clear pattern. This directly informs, but does not resolve, ID-7B's
own §22/§23 deferred questions.

## 21. Config-snapshot stratification — a real, notable operational difference

| `config_snapshot_id` | Episodes | Qualified | Qualified rate |
|---|---|---|---|
| `cfg-host-ops` (scheduled cycle) | 3,217 | 648 | 20.14% |
| `cfg-fast-revalidation` (FAST tier) | 283 | 49 | 17.31% |
| `cfg-full-validation` (owner "Validate All") | 3,117 | 86 | **2.76%** |
| `cfg-symbol-validate` | 7 | 0 | 0.0% (n too small) |

`cfg-full-validation`'s qualified rate is an order of magnitude lower
than the scheduled-cycle path — a real, notable difference worth
flagging for future attention (plausibly a broader/less-pre-filtered
universe, or different timing characteristics of ad hoc owner-triggered
runs), but **not investigated further here** — this milestone confirmed
no methodology/blueprint version differs across these paths (§6), so
this is an operational-population characteristic, not a methodology
drift concern, and is out of this milestone's scope to explain.

## 22. Reconstructed-cohort limitations (honest, explicit)

- **LONG-only**: no SHORT episodes exist to characterize (§9) — a hard
  data boundary, not a methodology gap this cohort can close.
- **Market-time replay only** (§5) — not a claim about historical
  real-time system knowledge.
- **No comparison population**: this milestone did not compute MFE/MAE/
  T1/T2 for non-`QUALIFIED` `TRADE` episodes, so the outcome figures in
  §16 cannot yet be read as "QUALIFIED episodes outperform
  non-QUALIFIED ones" — that comparison is a natural next question, not
  answered here.
- **Small session count** (20 distinct dates) constrains any future
  chronological calibration split (§10).
- **Episode-first-checkpoint only** for the primary cohort — the
  observation-level (full 96,985-row) cycle-to-cycle evolution was not
  exhaustively reconstructed in this milestone (§7, §17 [sic — see
  below]); a full-population run was started as a lower-priority,
  time-permitting supplementary pass and had not completed at the time
  this document was written. If it completes, its results can be
  incorporated in a future continuation without invalidating anything
  here, since the episode cohort is a strict subset by construction
  (first checkpoints of the same underlying decisions).
- **Recent-M5-structural-extremum and DarvaX-level candidates were not
  evaluated** — no predeclared lookback authority for the former; the
  latter is explicitly out of scope (cross-track isolation, §24).

## 23. ID-6 SHORT asymmetry — impact quantified, not fixed

Fully quantified (§9): zero `SHORT` decisions of any type exist in
`db/athena.db`. This is stronger and more precise than ID-7B's original
framing ("EQ v0's formula would rarely qualify a SHORT setup") — the
actual finding is that no SHORT decision population exists for EQ to be
tested against at all. Whether this reflects the `intraday-momentum`
strategy profile's own design, the specific ~4-week market period
sampled, a scoring/gate configuration characteristic, or something else
is **not determined here** — that would require its own separately
authorized investigation into the Decision/scoring/strategy layer,
outside both ID-6's and ID-7's boundaries. **No ID-6 change made or
proposed.**

## 24. Cross-track isolation

Zero EMR (`explosive_move/`) code, thresholds, or labels imported or
referenced. Zero DarvaX code, config, or Fibonacci/structural levels
used or queried. Both remain fully untouched by this milestone.

## 25. Files and validation

Research script(s) and the intermediate SQLite results cache live under
the session scratchpad (outside the tracked repository), never under
`src/`. This document is the sole tracked artifact besides the tracking-
doc updates listed in the return report. `git diff --check` and
`git status --short` (repo root) are both clean — zero source, schema,
or config changes.
