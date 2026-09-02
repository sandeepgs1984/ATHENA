# ID-6B.1B — Quality-Adjusted Policy Baseline & Wider TRADE Audit

**Status:** Analysis complete. Read-only research. No production code changed.
**Date:** 2026-09-02
**Depends on:** ID-6B.1 (owner approved/closed), ID-6B.1A (owner approved/closed,
Option C — artifact-owned availability — ratified).
**Authorizes only:** ID-6B.1B. Does **not** authorize ID-6B.2, ID-6C, ID-6D,
ID-6E, ID-7, or EM-6.

---

## 1. Executive summary

Applying the owner-ratified Option C (artifact-owned availability) correctly to
both the original ID-6B.1 window and a materially wider, TRADE-representative
window shows the candidate v0 candidate-readiness rule is **robustly evaluable
(≈99.6%–100%) and stable in prevalence (≈17.6%–24.2%)** across every sample
size tested, and that the chronic M15 off-grid `SessionDataQuality` condition
found in ID-6B.1A has **negligible practical effect** on that evaluability —
because the rule's actual M15 dependency (a last-N-by-value trend read, not a
since-open due-set) almost never trips on the off-grid condition. M15 is
classified **NON-BLOCKING TECHNICAL DEBT** for this v0 candidate rule (§15).
WATCH and TRADE show the same evaluability and the same directional evidence
pattern under quality-adjusted evaluation, with TRADE running consistently a
few points higher on every named field — a prevalence difference, not a
structural one — so the existing owner decision (same methodology for both,
canonical `Decision` type preserved) stands (§12). Recommendation: **FREEZE V0
POLICY WITH EXPLICIT LIMITATION** (§17).

## 2. Owner decisions recorded as frozen inputs to this milestone

- ID-6B.1A: **OWNER APPROVED / CLOSED.**
- Session-data-quality policy: **Option C (artifact-owned availability)
  RATIFIED.** The candidate rule's evaluability is governed by whether each
  input artifact it actually consumes is available — not by the coarse,
  session-level `SessionDataQualityStatus` enum, which can be
  `EXPECTED_BAR_MISSING` for a timeframe the rule doesn't structurally need at
  that moment.
- ID-6B.1B: **AUTHORIZED TO START** (this document).
- ID-6B.2: **NOT AUTHORIZED.**
- Preserved without re-litigation in this milestone: WATCH/TRADE share one
  methodology unless a *structural* reason is found (not raw prevalence
  alone); OR15/OR30 remain contextual/support evidence and are not inputs to
  the candidate-policy evaluability contract; `DISQUALIFIED_FOR_SESSION`
  remains off/unused in v0; `CONFIRMED_BY_POLICY` remains deferred/unused
  regardless of this milestone's outcome; no additive/weighted qualification
  score; missing evidence is never treated as bearish evidence; indirect
  `Decision` provenance stays conservative per ADR-013; no new numeric
  threshold is invented; the candidate rule remains research-only.

## 3. Primary questions this milestone answers

- **A (quality-adjusted policy question).** After correctly applying Option
  C, what fraction of candidate-checkpoint observations is genuinely
  evaluable, and how often does the candidate rule match among the evaluable
  population?
- **B (TRADE representativeness question).** Across a wider window with
  genuinely diverse TRADE-producing sessions, do WATCH and TRADE continue to
  support one common methodology?

## 4. Trend-contract audit (mandatory, source-level, no code changed)

Read directly from `src/athena/intraday/engine.py` (`_aggregate_trend`) and
`src/athena/intraday/models.py` (`IntradayTrendLabel`, `TimeframeTrendEvidence`,
`IntradayTrendContext`):

- The aggregate trend label has four possible values: `BULLISH`, `BEARISH`,
  `MIXED`, `UNKNOWN`.
- `BULLISH` is returned **only** when `five_min.bullish is True` **and**
  `fifteen_min.bullish is True`. `BEARISH` is symmetric (`is False` on both).
  `MIXED` requires both legs to be non-`None` and to disagree. If **either**
  leg's `bullish` field is `None` (unavailable), the aggregate is `UNKNOWN` —
  never `BULLISH`/`BEARISH`/`MIXED`.
- Consequence: **the pre-existing aggregate `BULLISH` measurement in ID-6B.1's
  own harness already represents genuine dual-timeframe (M5+M15) agreement.**
  No correction to the candidate rule's own formula was required — ID-6B.1's
  `candidate_policy_match` field, which consumes the aggregate trend label,
  was never silently treating a single-timeframe result as dual-timeframe
  confirmation.
- What *was* missing from ID-6B.1's own harness was **evaluability tracking
  at the component level** — the harness records `five_min_bullish` /
  `fifteen_min_bullish` as raw fields, but never asked "was each of these
  legs *available* in the first place, independent of its direction?" That
  question is what this milestone's `_dual_timeframe_evaluable` /
  `_m5_only_evaluable` predicates answer (§5).
- The M15 trend leg is retrieved via `list_candles_recent(limit=100,
  as_of=...)` — an ID-5E-bounded, **last-N-by-count** read, with
  `fifteen_min_sma_period=5` (config) meaning only 5 raw M15 closes from
  anywhere in the last 100 rows are needed. This is a fundamentally different
  retrieval contract from `SessionContext`'s since-open, exact-grid due-set
  check that produces `EXPECTED_BAR_MISSING`. Off-grid M15 bars remain
  chronologically meaningful and usable to this retrieval path; they only
  fail the *grid-alignment* check `SessionContext` performs, which the trend
  engine never consults.
- No production trend behavior was altered. This section is a documentation
  of existing behavior, not a proposal to change it.

## 5. Quality-adjusted evaluability contract (research-only; not a production enum)

`EVALUABLE_FOR_CANDIDATE_POLICY` (dual-timeframe variant, matching the
existing candidate rule's four named input groups):

```
vwap_available
AND five_min_available            (M5 trend leg present)
AND fifteen_min_available         (M15 trend leg present)
AND (rs_stock_vs_market != UNKNOWN
     OR rs_stock_vs_sector != UNKNOWN
     OR rvol_available)
```

A relaxed research variant, `_m5_only_evaluable`, drops the
`fifteen_min_available` requirement entirely, to isolate exactly how much of
the non-evaluable population is attributable to M15 specifically versus
everything else (VWAP / RS / RVOL).

Both are a simple "each named input group must have some available signal"
reading, per the owner's own §5 example wording — not full three-valued
(Kleene) short-circuit evaluation of the underlying rule expression. Neither
consumes Gap, OR15/OR30, or Sector Health, since the candidate rule itself
never reads those artifacts.

Implementation: [id6b1b_quality_adjusted_policy_baseline.py](../../src/athena/data/id6b1b_quality_adjusted_policy_baseline.py).

## 6. Missing-input research policy

An observation whose evaluability contract fails is recorded as
**`NOT_EVALUABLE`** — never as a policy-false match and never as bearish
evidence. Every rate in this report is reported **both** as a population rate
(denominator = all observations) and an evaluable-only rate (denominator =
evaluable observations only), exactly as the owner required. The two rates
are consistently within ~0.1 percentage points of each other across every
sample in this report (§8), which is itself evidence that non-evaluability is
rare enough not to distort the measurement either way.

## 7. Candidate rule variants measured

| Variant | Definition |
|---|---|
| **Dual-timeframe** (== existing `candidate_policy_match`) | VWAP positive AND aggregate trend `BULLISH` (which, per §4, already requires M5 **and** M15 bullish) AND (RS support OR RVOL support) |
| **M5-only** (relaxed) | VWAP positive AND M5 leg bullish (ignores M15 entirely) AND (RS support OR RVOL support) |

No further combinations were brute-forced, per the owner's explicit
instruction.

## 8. Option C effect — same 5-session/6-checkpoint window as ID-6B.1

Re-analyzed from ID-6B.1's own existing JSONL artifacts (no replay needed —
the harness already records the needed component fields).

| Sample | N | Dual-TF evaluable | Dual match, population | Dual match, evaluable | M5-only match, population |
|---|---:|---:|---:|---:|---:|
| Original capped (370 obs, `per_type=10`) | 370 | 100.00% | 17.57% (65) | 17.57% (65) | 21.35% (79) |
| Uncapped (7,144 obs, `per_type=1000`, from ID-6B.1A) | 7,144 | 99.55% | 20.53% (1,467) | — | 24.19% (1,728) |

For the uncapped 7,144-observation same-window sample, only **32
observations (0.45%)** were non-evaluable: 2 due to `m15_trend_unavailable`,
30 due to `vwap_unavailable` combined with both RS legs `UNKNOWN` and RVOL
unavailable. **M15 specifically accounted for 2 of 7,144 observations
(0.03%).** Flicker (later-checkpoint drop to no-match after an earlier match,
among instrument/session/decision_type groups with 2+ checkpoints):
37.84% (same-window capped) — full detail in
`artifacts/research/id6b1b/same_window_capped_analysis.json` and
`same_window_uncapped_analysis.json`.

**Conclusion:** applying Option C correctly to the original window changes
essentially nothing about the candidate rule's own evaluability or match
rate — the M15 `EXPECTED_BAR_MISSING` condition ID-6B.1A found does not
propagate into this rule in any material way.

## 9. Wider-window selection procedure (stated before analyzing evidence-policy prevalence)

Selection rule, applied and reported **before** any policy-match analysis was
run against the wider window:

1. Surveyed real `decisions` table counts for every trading date available in
   `db/athena.db` (2026-07-31 through 2026-09-02, 24 calendar dates, 20 actual
   trading sessions after weekends).
2. Found TRADE-type decisions exist on 20 consecutive sessions
   (2026-07-31–2026-08-27), and **zero** on the 4 most recent sessions
   (2026-08-28, 08-31, 09-01, 09-02) — the reason ID-6B.1's original 5-session
   window (2026-08-26–09-01) captured almost no TRADE representation.
3. Selected the **10 most recent consecutive trading sessions immediately
   preceding ID-6B.1's own window**: 2026-08-14, 08-17, 08-18, 08-19, 08-20,
   08-21, 08-24, 08-25, 08-26, 08-27 (correctly skips the 08-15/08-16
   weekend). This is the smallest consecutive window that gives materially
   broader real TRADE representation, per the owner's instruction — it was
   not chosen by inspecting which sessions the candidate rule matches best.
4. Same six deterministic checkpoints as ID-6B.1: `09:30, 09:45, 10:00, 11:00,
   13:00, 14:30`.
5. No cap applied (`per_type=1000`, effectively uncapped for this window's
   true population) — see §11 for the scale decision.

## 10. TRADE temporal distribution, wider window

| Session | TRADE | WATCH | Distinct instruments |
|---|---:|---:|---:|
| 2026-08-14 | 1,267 | 910 | 375 |
| 2026-08-17 | 991 | 1,071 | 370 |
| 2026-08-18 | 689 | 701 | 364 |
| 2026-08-19 | **0** | 1,011 | 188 |
| 2026-08-20 | 632 | 904 | 376 |
| 2026-08-21 | 1,184 | 997 | 373 |
| 2026-08-24 | 890 | 1,040 | 377 |
| 2026-08-25 | 5 | 1,160 | 230 |
| 2026-08-26 | 1,279 | 957 | 378 |
| 2026-08-27 | 197 | 1,197 | 370 |
| **Total** | **7,134** | **9,948** | — |

**Correction to a working assumption made mid-milestone:** 2026-08-19 turned
out to have **zero** TRADE observations (not "all 10 sessions have TRADE
representation" as initially assumed while only the population count had been
computed) and 2026-08-25 has only 5 (negligible). 8 of the 10 sessions carry
materially non-trivial TRADE volume. This does not change the selection
procedure (§9) or its validity — the window is still overwhelmingly more
TRADE-representative than the original — but it is reported here rather than
silently corrected, since the owner's instructions require reporting facts as
found.

Concentration: top-1 session (2026-08-14) carries 17.93% of all TRADE
observations; top-3 sessions carry 52.28%. Not dominated by a single session.
Sessions with any TRADE: 9/10. Sessions with any WATCH: 10/10.

Compared with ID-6B.1's original window (1,476 TRADE observations, confined
to 2 of 5 sessions: 2026-08-26 = 1,279, 2026-08-27 = 197, with zero TRADE on
2026-08-28/08-31/09-01): the wider window carries **4.8× more TRADE
observations**, spread across **9 distinct sessions instead of 2** — a
materially broader TRADE sample, as required.

## 11. Scale and replay design

ID-6B.1A's own uncapped 5-session/6-checkpoint replay (7,144 observations)
took 194.591s. A direct SQL count against `db/athena.db`, mirroring
`candidates_at`'s own ranked/`row_number()`-per-instrument query with no
per-type cap, estimated the wider 10-session window's true uncapped
population at **17,082** candidate-checkpoint observations — not
"unnecessarily huge" relative to that precedent (≈2.4×). The full uncapped
replay was run rather than an artificial stratified cap, using ID-6B.1's own
unmodified `run_baseline(session_dates=<10 dates>, checkpoints=<same 6>,
per_type=1000)` (no harness code changed). It completed in **418.469s**,
producing exactly **17,082 observations** — matching the SQL estimate
exactly, confirming no silent capping occurred. No alphabetical top-N bias
was introduced because no cap was applied at all.

Artifacts: `artifacts/research/id6b1b/wider_window/id6b1_observations.jsonl`
(22.7 MB, gitignored), `id6b1_summary.json`
(`analysis_sha256=a9e7997c8701b9c4c1073d9bd78629c1b77ec8272d81c4704e4d4a4d1a311c64`).

## 12. WATCH vs TRADE comparison, wider window, quality-adjusted

| Metric | TRADE (N=7,134) | WATCH (N=9,948) | Difference |
|---|---:|---:|---:|
| Evaluable | 99.47% | 99.77% | −0.30pp |
| VWAP positive rate | 44.60% | 37.88% | +6.72pp |
| M5 bullish rate | 48.36% | 46.09% | +2.27pp |
| M15 leg available | 99.96% | 99.99% | −0.03pp |
| M15 bullish rate (when available) | 52.46% | 46.01% | +6.45pp |
| Dual-timeframe (aggregate) bullish rate | 35.24% | 32.35% | +2.89pp |
| RS support rate | 57.71% | 52.56% | +5.15pp |
| RVOL support rate | 26.79% | 23.03% | +3.76pp |
| Candidate match, population | 24.17% | 19.93% | +4.24pp |
| Candidate match, evaluable | 24.30% | 19.98% | +4.32pp |

**Finding:** TRADE runs consistently a few points higher than WATCH on
*every* named field — VWAP positivity, both trend legs, RS, RVOL, and the
combined candidate match rate — with **no reversal, no collapse, and no
field where the two decision types diverge structurally** (e.g., neither
shows a field the other lacks, and evaluability is effectively identical for
both, 99.47% vs 99.77%). This is a uniform prevalence shift consistent with
TRADE being, by construction, the stronger of the two `Decision` outcomes —
not evidence of a different underlying methodology. Per the owner's standing
instruction, a raw prevalence difference alone does not justify separate
methodology; no structural reason was found here. **WATCH and TRADE continue
to support one common candidate-readiness methodology, and the canonical
`Decision` type is preserved unmodified.**

## 13. Checkpoint / session-time stability, wider window

| Checkpoint | Observations | Evaluable % | Match %, population | Match %, evaluable |
|---|---:|---:|---:|---:|
| 09:30 | 2,397 | 99.62% | 22.95% | 23.03% |
| 09:45 | 2,794 | 99.64% | 27.42% | 27.51% |
| 10:00 | 2,983 | 99.63% | 24.47% | 24.56% |
| 11:00 | 3,034 | 99.64% | 18.39% | 18.46% |
| 13:00 | 2,945 | 99.66% | 20.20% | 20.27% |
| 14:30 | 2,929 | 99.66% | 17.34% | 17.40% |

Descriptive pattern only, no threshold invented: evaluability is
**essentially flat (99.6%–99.7%) across the entire trading day** — the rule
is not more or less usable early vs. late. Match rate **peaks shortly after
the open (09:45, 27.5%)**, then **declines through the day to its lowest
point at the final checkpoint (14:30, 17.4%)** — a pattern consistent with
intraday momentum/confirmation naturally fading rather than a data-quality
artifact, since evaluability itself does not degrade at the same checkpoints.

## 14. Flicker, corrected quality/evaluability semantics, wider window

Among instrument/session/decision_type groups observed at 2+ checkpoints
(3,755 such groups in the wider window): **1,493 (39.76%)** show the pattern
"matched at an earlier checkpoint, then did not match at a later checkpoint
in the same session." This is close in order of magnitude to the same-window
uncapped figure (46.43%, §8/prior milestone), confirming flicker is a real,
stable property of the checkpoint-level candidate rule across sample sizes —
not small-sample noise. **This finding alone remains sufficient reason not to
invent a persistence/confirmation rule** — `CONFIRMED_BY_POLICY` stays
deferred/unused (§19).

## 15. M15 practical-impact classification

Evidence assembled across all four samples in this report:

| Sample | N | M15-caused non-evaluability |
|---|---:|---:|
| Same-window, capped (370) | 370 | 0 |
| Same-window, uncapped (7,144) | 7,144 | 2 (0.03%) |
| Wider window (17,082) | 17,082 | 4 (0.02%) |

**Classification: NON-BLOCKING TECHNICAL DEBT.** M15's chronic off-grid
`SessionDataQuality` condition (ID-6B.1A) is real, documented, and
unrepaired, but it does **not** meaningfully block this v0 candidate policy —
because the policy's actual M15 dependency is a last-N-by-value trend read
(§4) that almost never depends on grid alignment, so genuine M15
unavailability (the `bullish` field being `None`) is nearly nonexistent in
practice (≤0.03% of every sample measured, at both small and large N). A
defensible v0 methodology can operate today without unsafe reliance on
repaired M15 data. **No M15 repair milestone is required as a prerequisite
for a future Entry Qualification engine built on this candidate rule.** If a
future track wants to pursue M15 repair anyway (e.g., to improve
`SessionContext`'s own quality signal for reasons unrelated to this rule),
that would be separate, future-scoped work — parity with `live_m5_settlement_repair.py`
generalized to `Timeframe.M15` — not proposed or scoped further here, and not
authorized by this milestone.

## 16. No outcome optimization

No trade outcome, MFE/MAE, time-to-target, +1%/+1.5% threshold, or journal
row was read or used anywhere in this milestone to select, tune, or justify
the candidate rule or either evaluability variant. Every measurement in this
report answers "is the policy coherent, available, selective, and
structurally stable?" — never "does it make money?"

## 17. Policy-freeze recommendation

**FREEZE V0 POLICY WITH EXPLICIT LIMITATION.**

Rationale: the candidate rule is evaluable for 99.5%+ of real checkpoint
observations across both a small and a 17k-observation sample; its
population and evaluable-only match rates agree to within ~0.1pp in every
sample, meaning Option C's correction changes nothing material; WATCH and
TRADE share the same methodology with no structural divergence (§12);
checkpoint stability is descriptively sensible (§13); and M15 is confirmed
non-blocking (§15). None of this constitutes evidence the policy is
*profitable* — only that it is well-defined, almost always computable, and
stable under the inputs it actually consumes. The explicit limitation to
attach to the freeze: **known, persistent checkpoint-level flicker (≈40%)
means this v0 policy is a point-in-time signal, not a persistence/confirmation
signal** — any future engine built on it must not silently assume a match at
one checkpoint predicts a match at the next.

## 18. Proposed v0 engine semantics (proposal only — no implementation)

Using existing contracts from ID-6A/ID-6A0 (no new types invented):

- **`OUT_OF_SCOPE`** — instrument/session outside the entry-qualification
  candidate universe entirely (unchanged from ID-6A's contract).
- **`UNKNOWN`** — the quality-adjusted evaluability contract (§5) fails: one
  or more required input groups (VWAP, M5 trend, M15 trend, RS-or-RVOL) is
  genuinely unavailable. Never treated as bearish.
- **`NOT_YET`** — evaluable, but the candidate rule (§7, dual-timeframe
  variant) does not currently match.
- **`QUALIFIED`** — evaluable, and the candidate rule currently matches.
  Given §14's flicker finding, `QUALIFIED` must be understood and documented
  as a point-in-time state only, re-derived fresh at every checkpoint — never
  cached or treated as sticky.
- **`EXPIRED`** — reserved for a future session-boundary/time-decay rule; not
  populated by v0 logic as specified here.
- **`DISQUALIFIED_FOR_SESSION`** — remains off/unused in v0, per the owner's
  standing instruction (§2).
- **Evidence-finality output:** conservative per ADR-013 (§20) — when the
  bound `Decision`'s provenance relative to provisional M5 data cannot be
  established, the engine must not claim `QUALIFIED` is stable evidence, but
  must also not force an irreversible rejection; it should carry a
  provisional/finality flag alongside the state, not fold it into the state
  itself.
- **Confirmation output:** none in v0 — `CONFIRMED_BY_POLICY` stays
  unpopulated (§19).
- **Reason categories:** for `UNKNOWN`, the specific missing input group(s)
  (mirrors §6's `non_evaluability_reasons` breakdown); for `NOT_YET`, which
  named condition(s) of the candidate rule failed (VWAP / M5 trend / M15
  trend / RS-and-RVOL).
- **WATCH/TRADE handling:** identical methodology for both, per §12 — no
  type-specific branching.
- **Missing-evidence behavior:** always `UNKNOWN`, never `NOT_YET`
  (missing ≠ bearish, per the owner's standing instruction).

This is a semantics proposal only. **No engine code, persistence, workflow
wiring, API, or UI was written or is proposed to be written under this
milestone.**

## 19. Confirmation

`CONFIRMED_BY_POLICY` remains deferred and unused in this milestone's
recommendation, independent of the freeze outcome above, per the owner's
standing instruction and independently reinforced by §14's flicker finding —
inventing a persistence/confirmation rule without further owner-authorized
research would mean guessing a threshold with no evidentiary basis.

## 20. Indirect Decision provenance

No `DecisionEngine` code was read, modified, or newly relied upon beyond what
ID-6B.1's own harness already used. Per ADR-013, this milestone does not
claim the historical `Decision` rows underlying any observation had
guaranteed-final (non-provisional) M5 evidence at the time they were
persisted — that provenance question is not resolved here and is explicitly
deferred to whatever future engine consumes these findings (§18's
evidence-finality proposal exists precisely to carry that uncertainty
forward conservatively, rather than resolving it now).

## 21. M15 repair track boundary

Not touched. `live_m5_settlement_repair.py` was read (§4/ID-6B.1A) but not
modified, and no M15 equivalent was created. Per §15, no M15 repair is
recommended as a prerequisite; if pursued later, it must be separately
owner-authorized and scoped as its own milestone.

## 22. Read-only / production safety

- All database access used SQLite `file:...?mode=ro` URI with
  `PRAGMA query_only=ON`, verified in ID-6B.1A's own test suite against a
  live `INSERT` rejection.
- No DB writes. No provider/network calls (confirmed — the wider-window
  replay reused ID-6B.1's own harness, which reads exclusively from the
  local SQLite store).
- No production engine, persistence, workflow, API, or UI code was created or
  modified.
- No EMR or DarvaX code was read or touched.
- New artifacts were written only to new, gitignored directories under
  `artifacts/research/id6b1b/`; no existing raw artifact file was modified.

## 23. Artifacts produced

| Path | Description |
|---|---|
| `src/athena/data/id6b1b_quality_adjusted_policy_baseline.py` | New research module: quality-adjusted evaluability + candidate-rule variants; re-analyzes existing JSONL, no replay required |
| `tests/data_layer/test_id6b1b_quality_adjusted_policy_baseline.py` | 6 new focused, non-vacuous unit tests |
| `artifacts/research/id6b1b/same_window_capped_analysis.json` | §8 same-window, 370-obs re-analysis (gitignored) |
| `artifacts/research/id6b1b/same_window_uncapped_analysis.json` | §8 same-window, 7,144-obs re-analysis (gitignored) |
| `artifacts/research/id6b1b/wider_window/id6b1_observations.jsonl`, `id6b1_summary.json` | §9-11 fresh wider-window replay, 17,082 observations (gitignored) |
| `artifacts/research/id6b1b/wider_window_analysis.json` | §12-15 wider-window quality-adjusted analysis (gitignored) |
| `docs/research/ID-6B.1B-QUALITY-ADJUSTED-POLICY-BASELINE.md` | This report |

## 24. Validation

- **Focused tests:** 6 new tests in
  `tests/data_layer/test_id6b1b_quality_adjusted_policy_baseline.py`, all
  non-vacuous (each asserts a specific true/false outcome tied to a specific
  input construction, e.g. explicitly proving `_dual_timeframe_evaluable`
  flips to `False` only when `fifteen_min_available` is `False`, and that
  `_m5_only_evaluable` does *not* flip in that same case). Combined with
  ID-6B.1A's 3 existing tests: **11/11 passed** in the `data_layer` package.
- **Full `tests/data_layer/` suite:** 428 passed, 0 failed.
- **Determinism:** re-ran `id6b1b_quality_adjusted_policy_baseline.py`
  against the frozen wider-window JSONL a second time — byte-identical
  output (`sha256=af28e7ee9828f67683050b2f55a6ce6670427f5b7770bc256dda1d21c83cbca1`
  both times).
- **Ruff:** `ruff check` on both new files — all checks passed.
- **`git diff --check`:** exit 0, no whitespace errors.
- **`git status --short`:** two new untracked files only —
  `src/athena/data/id6b1b_quality_adjusted_policy_baseline.py` and
  `tests/data_layer/test_id6b1b_quality_adjusted_policy_baseline.py` (plus
  gitignored `artifacts/research/id6b1b/**`, not shown by git status).
- **No production DB writes:** confirmed — read-only connections throughout.

## 25. Limitations

- The wider window (2026-08-14–08-27) is still confined to real historical
  data currently present in `db/athena.db`; it does not include the 4 most
  recent sessions, which have zero TRADE decisions for reasons out of scope
  for this milestone (noted, not root-caused, in ID-6B.1B's predecessor
  survey).
- 2026-08-19 and 2026-08-25 contribute negligible TRADE volume to the wider
  window (0 and 5 observations respectively) — the window's TRADE
  representativeness rests effectively on 8 of its 10 sessions.
- This milestone establishes *coherence, availability, selectivity, and
  structural stability* of the v0 candidate rule. It makes **no claim** about
  trade profitability, win rate, or any outcome-based measure — that
  question is explicitly out of scope (§16) and would require separate,
  owner-authorized, outcome-aware research.
- Indirect `Decision` provenance (§20) remains an open, conservatively-handled
  question, not a resolved one.

## 26. Status and next steps

This milestone (ID-6B.1B) is complete. No later milestone (ID-6B.2, ID-6C,
ID-6D, ID-6E, ID-7, EM-6) has been started. The proposed v0 engine semantics
(§18) are a proposal only, pending owner review and explicit authorization of
a future implementation milestone.

## 27. Suggested commit message

```
docs(review): quality-adjusted v0 candidate policy baseline (ID-6B.1B)

- Audited the intraday trend contract at source level and confirmed the
  aggregate BULLISH label already requires genuine M5+M15 agreement, so
  ID-6B.1's own candidate_policy_match measurement needed no correction.
- Defined a research-only quality-adjusted evaluability contract (Option C)
  and re-analyzed ID-6B.1's existing same-window observations without a
  replay, finding 99.55-100% evaluability and near-identical population vs.
  evaluable-only match rates.
- Selected and replayed a deterministic, materially wider 10-session TRADE-
  representative window (2026-08-14 to 2026-08-27, 17,082 observations,
  4.8x more TRADE observations than ID-6B.1's original window) via ID-6B.1's
  own unmodified harness.
- Found M15's chronic off-grid condition (ID-6B.1A) causes non-evaluability
  in <=0.03% of every sample tested -- classified NON-BLOCKING TECHNICAL
  DEBT, not a prerequisite for a future Entry Qualification engine.
- Compared WATCH vs TRADE under quality-adjusted evaluation: consistent
  uniform prevalence shift (TRADE a few points higher on every field), no
  structural divergence -- preserves the single shared methodology decision.
- Recommended FREEZE V0 POLICY WITH EXPLICIT LIMITATION (checkpoint-level
  flicker ~40% means the policy is point-in-time only, not persistence).
- Added 6 focused, non-vacuous tests for the new quality-adjusted analyzer.

Per ATHENA-001 amendment 7. No production code, persistence, workflow, API,
or UI changed. Confirmation and disqualification remain deferred/unused.
```
