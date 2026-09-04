# ID-7B — Entry / Risk Methodology Discovery & Freeze

**Status: METHODOLOGY PARTIALLY FROZEN — EVIDENCE REQUIRED for numeric
thresholds. Structural methodology (gates, hierarchy, representation
shapes, freshness dimensions) frozen with source/evidence grounding.
Zero production code, schema, workflow stage, or engine implemented.**

## 1. Purpose

Given an exact `TRADE` `Decision` + exact `QUALIFIED` `EntryQualification`
(ADR-015/ID-7A0.1's frozen upstream eligibility contract), determine what
deterministic evidence makes `EntryActionability` `UNKNOWN` /
`NOT_ACTIONABLE` / `ACTIONABLE`, and — when `ACTIONABLE` — what entry,
invalidation, and reward evidence to expose, and how fresh that evidence
must be. Methodology only: no domain class, schema, `WorkflowStage`, or
engine is created here.

## 2. The decisive empirical fact: zero real (TRADE, QUALIFIED) history

Before any methodology design, the real production database was queried
read-only (`mode=ro`, `PRAGMA query_only=ON`):

```sql
SELECT COUNT(*) FROM entry_qualifications eq
JOIN decisions d ON d.decision_id = eq.decision_id
WHERE eq.state='QUALIFIED' AND d.decision_type='TRADE';
-- 0
```

All 11,986 persisted `entry_qualifications` rows are bound to `WATCH`
decisions (`NOT_YET|WATCH: 8443, QUALIFIED|WATCH: 1913, UNKNOWN|WATCH: 985,
EXPIRED|WATCH: 645`) — **zero** rows of any state are bound to a `TRADE`
decision. Root cause, confirmed by timestamp comparison: all 96,985
`TRADE` decisions in the database were made **2026-07-31 through
2026-08-27** — entirely before `entry_qualifications` persistence went
live (2026-09-03, per ID-6E.2). No genuine `TRADE` decision has recurred
in the ~2 days since. This is benign chronology, not a defect — but it
means **this methodology is designed with zero real historical
`(TRADE, QUALIFIED)` episodes to validate against.** Every numeric
threshold question in this document is answered accordingly: structural
methodology is frozen from real, general-population market evidence and a
purpose-built empirical freshness analysis (§4); numeric cutoffs specific
to the `(TRADE, QUALIFIED)` population itself are explicitly deferred,
not invented.

## 3. Source audit summary (full citations; nothing paraphrased into new semantics)

- **`IntradaySignalSet`** (`src/athena/intraday/models.py:120-146`):
  `vwap: VwapEvidence, trend: IntradayTrendContext, or15/or30:
  OpeningRangeEvidence, relative_strength: RelativeStrengthContext, gap:
  GapContext, relative_volume: RelativeVolumeContext, data_quality`.
- **VWAP** (`indicators/calculations.py:196-225`): session-anchored
  cumulative VWAP from completed M5 bars only. `VwapEvidence.relation`
  (`ABOVE_VWAP/BELOW_VWAP/AT_VWAP/VWAP_UNAVAILABLE`) is the sign of
  `deviation_pct` (`intraday/engine.py:134-140`). `deviation_pct: Decimal
  | None` — a **real signed percentage distance**, already computed,
  zero new code (`models.py:106-117`).
- **Trend** (`intraday/engine.py:171-192`): `IntradayTrendLabel.BULLISH`
  iff M5 **and** M15 legs (each `close >= trailing SMA`) independently
  agree bullish; `BEARISH` iff both agree bearish; `MIXED` on
  disagreement; `UNKNOWN` if either leg unresolvable. Unanimous-agreement
  only — no weighting, no precedence rule exists.
- **`RelativeStrengthContext`** (`relative_strength_models.py:56-97`):
  categorical `*_relation` (`OUTPERFORMING/UNDERPERFORMING/MATCHING/
  UNKNOWN`) **plus** real signed differentials `stock_vs_market_pct`,
  `stock_vs_sector_pct`, `sector_vs_market_pct`.
- **`RelativeVolumeContext`** (`relative_volume_models.py:49-77`):
  categorical `relation` **plus** a real `rvol_ratio: Decimal | None`
  (current cumulative same-time-of-day volume ÷ historical average).
- **`OpeningRangeEvidence`** (`opening_range_models.py:80-145`,
  `opening_range_engine.py:284-306`): `formation.status`
  (`FORMING/COMPLETE/INCOMPLETE_DATA/NOT_AVAILABLE/NOT_APPLICABLE`),
  directional `breakout_event`
  (`UPSIDE_BREAKOUT_EVENT/DOWNSIDE_BREAKDOWN_EVENT/NO_EVENT/NOT_OBSERVED`),
  `max_extension_from_range_pct`, `current_extension_pct`,
  `returned_inside_range: bool | None`.
- **`GapContext`** (`gap_models.py:52-74`): `gap_pct`, `direction`
  (`GAP_UP/GAP_DOWN/FLAT/UNKNOWN`), fixed at session open — no
  gap-fill/-hold tracking exists.
- **`SessionPhase`** (`session/models.py:23-45`): exactly
  `NOT_A_TRADING_SESSION, PRE_OPEN, REGULAR, CLOSED` — no separate
  `PREMARKET`/`CLOSING` member; `PRE_OPEN` covers the whole pre-open
  window.
- **Completed-candle rule** (`session/engine.py:36-45`):
  `candle.ts_open + timeframe_minutes <= as_of` — the single authority
  every VWAP/trend/OR/RS/RVOL consumer reuses.
- **ATR**: `atr()`/`atr_series()` (`indicators/calculations.py:108-125`)
  are timeframe-agnostic, but in production are **only ever called on the
  D1 series** (`ops/owner_validation.py:936-946`; `TradePlan` consumes
  this same D1 ATR, `decision/engine.py:238-256`). **No M5/M15 ATR exists
  anywhere in the production path.** The sole ATR-normalization precedent
  in the repo is an isolated, D1-only EMR research module
  (`explosive_move/session_invariant_evidence.py:91-95`,
  `atr14_norm = atr14_val / closes[-1]`) — cross-track isolated, not
  reused here, cited only as a normalization-pattern precedent.
- **Quote/current price**: `Quote.last_price`
  (`domain/market.py:106-117`) is used **only** as a data-quality/
  freshness signal (`SessionDataQualityStatus.QUOTE_UNAVAILABLE`,
  `session/engine.py:359,374`) — never the price source for VWAP/trend.
  `EntryQualificationEngine.evaluate()` itself **never reads a raw
  price or `Quote` at all** — confirmed by full source read
  (`entry_qualification_engine.py`) — it consumes only the already-
  categorical relation enums. This means ID-7B reading the *magnitude*
  fields above (`deviation_pct`, `rvol_ratio`, `stock_vs_*_pct`) does
  **not** duplicate EQ's own boolean checks — it is a legitimate
  escalation from categorical to quantitative for a structurally
  different purpose (entry timing/risk, not qualification).
- **Evidence finality** (`entry_qualification_provenance.py:66-101`):
  `LIVE_M5_PROVISIONAL` iff `decision_type in (WATCH,TRADE) and
  session.phase is REGULAR` — provisionality is purely "today's
  still-open session," **not** "this specific bar is still forming."
  Even a fully completed M5 bar inside a `REGULAR` session carries
  `LIVE_M5_PROVISIONAL` (settlement repair has not run on it yet).
- **No normalized-distance/extension helper exists** anywhere in
  `intraday/`/`indicators/` (confirmed via targeted grep) beyond OR's own
  (non-ATR-normalized) `*_extension_pct` fields — an ATR- or
  VWAP-deviation-based extension measure for ID-7B is new *reuse* of
  already-computed inputs, not a new indicator.
- **`Candle`** (`domain/market.py:39-63`): OHLCV + `ts_open` +
  `timeframe` only — no `ts_close`, no precomputed swing/pivot fields.
  Any "recent local extremum" for invalidation must scan a candle
  sequence itself (a simple min/max over N completed bars — not a
  generic support/resistance engine).
- **Opening Range reliability** (`docs/research/PS-P9B-PORTFOLIO-OPENING-RANGE-SETUP-METHODOLOGY-REPLAY.md`,
  owner-reviewed 2026-09-04, real 35,232-observation replay): OR30 was
  only `COMPLETE` 68.54% of the time (OR15: 93.25%); 9,639/15,342 (62.8%)
  of observations with any OR event **returned inside the range
  afterward**; 524 observations showed simultaneous OR15-upside/
  OR30-downside conflict; **no owner-approved OR15/OR30 precedence
  exists** (§10, "METHODOLOGY_REQUIRED. Do not implement until the owner
  chooses..."); explicit prior boundary from PS-P9A: **"EntryQualification
  is context/confirmation only; QUALIFIED must not map directly to
  BREAKOUT."** This directly governs §7 below — OR is used, narrowly, as
  a structural *level* reference, never as a breakout-event gate.

## 4. Empirical freshness analysis (new, this milestone, real data)

The central question the authorization poses is whether a canonical
cycle's ≈9–10 minute duration (ID-7P0: median 560.6s) makes a `QUALIFIED`
checkpoint too stale for entry/risk semantics by the time it is
evaluated/consumed. This was tested directly against real M5 candle
history, read-only (`mode=ro`), rather than assumed.

**Method**: 60 randomly sampled instruments with substantial M5 history
(each &gt;1,000 candles), REGULAR-session hours only (09:15–15:25 IST),
full available history (2026-07-23 through 2026-09-04). For every
completed M5 bar, measured the price change to the close **two candles
later** (≈10 minutes — the closest whole-candle proxy for one canonical
cycle's duration), and separately tracked whether "price above/below
session VWAP" (computed the same way `VwapEvidence.relation` is) flips
across that same 10-minute gap. 138,454 real candle-pair samples.

**Absolute 10-minute price move (REGULAR session)**:

| median | mean | p75 | p90 | p95 | p99 |
|---|---|---|---|---|---|
| 0.093% | 0.154% | 0.191% | 0.351% | 0.503% | 0.969% |

**Same move, normalized as a fraction of the instrument's own typical
daily range** (median of `(D1 high − D1 low)/D1 close` over its last ≈60
trading sessions, per instrument):

| median | p75 | p90 | p95 | p99 |
|---|---|---|---|---|
| 3.86% | 7.74% | 13.72% | 19.26% | 35.57% |

**VWAP-side persistence over the same ≈10-minute gap** (138,454 pairs):
88.32% of the time, whether price is above or below session VWAP is
**unchanged**; 11.68% flip.

**Interpretation.** In the *typical* case, a canonical-cycle-old
checkpoint has barely moved (median 0.09% absolute, ≈4% of a typical
day's range) and the VWAP-side condition that helped qualify it is still
true 88% of the time. This does **not** support
`CANONICAL_CYCLE_FRESHNESS_NOT_ACCEPTABLE` — the architecture is not
fundamentally broken for the common case. But the **tail is real and
non-trivial**: at p90–p95, price has already consumed 14–19% of a
typical day's range in just the canonical cycle's own duration, and the
VWAP condition flips in roughly 1 in 9 cases. A methodology that treats
"was `QUALIFIED`" as sufficient on its own, with no active extension/
staleness gate, would be genuinely exposed in a material minority of
cases — exactly the "compensate for it after the fact" risk the
authorization warns against. **Conclusion: the extension/chase gate (§7)
and the evidence-age term of `is_currently_usable` (§10) must be real,
load-bearing gates in this methodology, not decorative ones** — with that
condition satisfied, Option 1 (canonical-cycle synchronous) remains
architecturally sufficient; no ADR-015 revision is required (see §17).

## 5. Upstream eligibility contract (carried forward, not reopened)

`EntryActionability` evaluation proceeds past a trivial `NOT_ACTIONABLE`
only when `Decision.decision_type == TRADE` **and** the exact bound
`EntryQualification.state == QUALIFIED` (identity = ADR-015's frozen
composite key). Any other combination (Decision not `TRADE`; EQ
`UNKNOWN`/`NOT_YET`/`EXPIRED`/`DISQUALIFIED_FOR_SESSION`/`OUT_OF_SCOPE`)
produces `NOT_ACTIONABLE` with the exact upstream reason preserved — this
was already frozen by ID-7A0/ID-7A0.1 and is not redesigned here.

## 6. WATCH behavior (carried forward)

Unchanged: a `WATCH`-bound EQ still produces an `EntryActionability` row,
`NOT_ACTIONABLE`, reason `UPSTREAM_DECISION_NOT_TRADE` — never silently
omitted.

## 7. Directionality — and an upstream gap this milestone must surface

`EntryActionability`'s own methodology is designed fully direction-
symmetric: every gate below mirrors correctly for `LONG`/`SHORT`
(`Direction`, reused from `Decision`), matching `TradePlan`'s own
existing bidirectional precedent. All raw evidence classes needed
already support this symmetrically — `BreakoutEvent` is explicitly
directional (`UPSIDE_BREAKOUT_EVENT`/`DOWNSIDE_BREAKDOWN_EVENT`), `VWAP
relation` and `trend label` have both-side values (`ABOVE_VWAP`/
`BELOW_VWAP`, `BULLISH`/`BEARISH`). There is no raw-evidence asymmetry
gap for ID-7B's own construction to silently paper over.

**A genuine, upstream (not ID-7B's own) asymmetry must be surfaced
honestly, per source (§3, full read of `entry_qualification_engine.py`):
EQ's own frozen v0 formula requires `VwapRelation.ABOVE_VWAP` **and**
`IntradayTrendLabel.BULLISH` unconditionally — there is no symmetric
"below VWAP and BEARISH" path to `QUALIFIED`. This means EQ's v0
methodology is directionally asymmetric (long-biased): a well-formed
`SHORT` setup (falling price, below VWAP, bearish trend) would need the
*opposite* of what EQ's formula actually checks, so it would essentially
never reach `QUALIFIED` under the current frozen formula. Since
`EntryActionability` is strictly downstream of `EQ=QUALIFIED`, this means
**in practice, `EntryActionability` will rarely if ever be reached for a
genuine `SHORT` opportunity today** — not because ID-7B excludes shorts,
but because the upstream ID-6 gate structurally does. ID-7B must **not**
redefine ID-6 (explicit authorization boundary) and does not attempt to.
This is recorded as an open, upstream gap (§18) for future owner
attention, not fixed here.

## 8. Entry representation

**Decision: trigger + allowable zone**, not a single fixed price (unlike
`TradePlan`'s `entry_low=entry_high=last_close`) and not an unbounded
open-ended zone. Rationale: `TradePlan` operates at daily granularity,
where a single snapshot price is reasonable because the whole system
re-evaluates once per day; `EntryActionability` exists specifically
because intraday timing needs finer resolution, and §4's own data shows
price is *already* not exactly where it was at the qualifying checkpoint
by the time evaluation/consumption happens — a single fixed price would
already be measurably wrong in a material share of cases. A trigger +
bounded zone remains meaningful over the artifact's realistic
consumption window instead of being instantly stale.

- **`trigger`**: the evidence anchor's own reference value at
  `entry_actionability_as_of` (§9's primary candidate: session VWAP
  value at that checkpoint — the same signal that qualified the setup,
  keeping the EQ→EntryActionability chain conceptually coherent).
- **`zone_low`/`zone_high`**: bounds derived from the *same* extension/
  chase tolerance used to gate `ACTIONABLE` (§7 of the authorization,
  §9 below) — the zone boundary and the chase limit are the same
  concept, not two independently invented ones.
- **`basis`**: an explicit tag naming which anchor was used (e.g.
  `VWAP_ANCHORED`) — never an opaque number with no stated origin.

No exact numeric zone width is frozen here (§13, deferred).

## 9. Entry-location validity & extension/chase (merged; see rationale)

The authorization's illustrative ordering lists "entry-location validity"
and "extension/chase treatment" as separate steps; for V0 they resolve to
the **same underlying check** — is current price still reasonably close,
in a volatility-aware sense, to the checkpoint's own evidence anchor —
so this methodology freezes them as one named gate.

**Primary anchor: VWAP `deviation_pct`** (already computed, zero new
code, directly available every cycle for every instrument with VWAP
available). Using the same signal EQ itself qualified on keeps the
methodology chain interpretable end-to-end. **Secondary/supplementary
candidate: D1-ATR-normalized distance** from the qualifying checkpoint's
reference price (mirrors both `TradePlan`'s own D1-ATR-based risk
framing and my own §4 daily-range normalization) — retained as an
alternative or supplementary normalization, not chosen exclusively over
VWAP deviation, since both are real, already-available (no new
indicator), and answer closely related but not identical questions
(distance from the *signal* vs. distance in *volatility units*).

**Gate: if the current VWAP-deviation-based (and/or ATR-normalized)
extension exceeds a threshold, `NOT_ACTIONABLE` (`ENTRY_TOO_EXTENDED`),
even though the bound EQ remains `QUALIFIED`.** This directly answers
the authorization's chase-risk question: yes, a `QUALIFIED` setup that
has already moved too far is `NOT_ACTIONABLE`. §4's empirical
distribution (median 10-min move ≈4% of daily range, p90 ≈14%, p95
≈19%) is the real evidence base for eventually calibrating this
threshold — **no specific cutoff number is frozen here** (§13).

## 10. Invalidation hierarchy

No generic support/resistance engine exists (confirmed, §3) and none is
invented. Hierarchy, evaluated in order, first coherent tier wins:

1. **VWAP-loss (primary)** — price closes back through session VWAP
   against the trade's direction on a completed M5 bar. Always available
   whenever VWAP itself is available; directly ties invalidation to the
   same dimension that qualified the trade ("the condition that made
   this actionable has reversed").
2. **Recent completed M5 structural extremum (secondary)** — the nearest
   local swing high/low against the trade's direction within the
   qualifying window, computed by scanning already-persisted completed
   M5 candles (a simple rolling min/max over N bars) — a real structural
   reference, not a generic S/R engine; exact N deferred (§13).
3. **Opening Range boundary — level only (tertiary)** — OR15's high/low
   (only when `formation.status == COMPLETE`, ≈93.25% availability per
   PS-P9B), used strictly as a price *level*, never via
   `breakout_event`/`returned_inside_range`/extension semantics (per
   PS-P9B's own explicit caution against those specific fields, §3).
4. **D1 ATR fallback (final)** — mirrors `TradePlan`'s own existing
   D1-ATR-based risk framing; used only when tiers 1–3 are unavailable
   or incoherent (e.g. `VWAP_UNAVAILABLE`), ensuring invalidation is
   never silently left undefined while ATR itself is computable.
5. **If none of the above is computable** (e.g. D1 ATR itself
   unavailable), invalidation is `UNKNOWN` — and the whole
   `EntryActionability` evaluation resolves to `UNKNOWN`
   (`INVALIDATION_UNAVAILABLE`), never a fabricated risk level and never
   a silently-omitted one.

No numeric stop distance/multiplier is frozen for any tier (§13).

## 11. Reward / target representation

**T1/T2 (~+1%/~+1.5%) status: `GOAL_BANDS_ONLY`.** No canonical
generalized support/resistance evidence exists to anchor a
"resistance-validated" target, and OR's own reliability caveats (§3)
disqualify it as a target-validation source. Reward is represented as
percentage-based goal-band reference points from the entry anchor
(`trigger`), explicitly **not** asserted as guaranteed or
structurally-validated targets — consistent with the product framing
already established before this milestone.

**Support/resistance dependency classification: `V0_DOES_NOT_REQUIRE_GENERIC_SR`.**
Reward (goal bands), invalidation (VWAP/local-extremum/OR-level/ATR),
and entry-location (VWAP-deviation/ATR-normalized) all use only evidence
that already exists — no generic support/resistance engine is a
prerequisite for a coherent V0.

## 12. Reward/risk (RR)

**Not automatically inherited as `RR=2.0`.** With zero real
`(TRADE, QUALIFIED)` outcome history, no empirical basis exists to
freeze a minimum RR gate. **Decision: RR is computed and exposed as an
informational value** (`reward_risk`: distance from `trigger` to a T1/T2
goal band ÷ distance from `trigger` to the invalidation level from §10)
**but does not gate `ACTIONABLE`/`NOT_ACTIONABLE` in V0.** This freezes
the methodology *shape* (a real, explainable reward/risk figure is
always surfaced when computable) while explicitly deferring any
minimum-RR requirement to a future, evidence-backed milestone.

## 13. Numeric-threshold authority audit (deferred, not invented)

The following candidate numeric thresholds were considered and are
**explicitly deferred** — no empirical authority sufficient to freeze
them exists today, and none is invented:

- Extension/chase cutoff (§9) — VWAP-deviation and/or ATR-normalized.
- Zone width (§8) — derives from the above once frozen.
- Local-extremum lookback window N (§10, tier 2).
- Minimum reward/risk (§12), if ever adopted as a gate.

§4's empirical distributions (10-minute price-move and VWAP-persistence,
from 138,454 real REGULAR-session candle-pair samples) are the
authoritative evidence base a future calibration milestone should use —
they are reported here precisely so no future threshold gets chosen
"because it sounds reasonable." No already-frozen authoritative ATHENA
constant exists that could substitute (D1 `atr_stop_multiple=1.5`/
`atr_target_multiple=3.0` are `TradePlan`'s own daily-granularity
constants, not intraday-appropriate, and not reused here without
justification the current evidence does not provide).

## 14. Freshness / currentness methodology (`is_currently_usable` ingredients)

Per ADR-015/ID-7A0.1's frozen dimension (B) — never persisted, always a
read-time derived predicate — ID-7B freezes its exact ingredients:

1. **Methodology state (A) == `ACTIONABLE`.**
2. **Exact bound EQ is still current** (§15).
3. **Evidence age** (`now − evidence_as_of`) **within a freshness
   policy** — dimensions frozen, numeric threshold deferred (§13);
   §4's distribution is the evidence base.
4. **Session state permits use** (§16 — `REGULAR` only).
5. **Evidence finality does *not* independently gate currentness** —
   see below.

**Provisional evidence can be currently usable.** Per the authorization's
own explicit instruction and ID-6's own precedent (EQ already
deliberately permits `LIVE_M5_PROVISIONAL` evidence to qualify), this
methodology does **not** treat `PROVISIONAL == unusable`. Evidence
finality/provisionality remains informational/audit context (dimension
C), reported alongside a currentness result, never silently conflated
with it.

## 15. Exact EQ currentness

Not "latest Decision id" alone (the authorization's own caution:
multiple EQ identities can exist for one Decision via distinct `as_of`
or `methodology_version`). **Frozen rule:** the bound EQ is current iff
its full composite key
(`instrument_id, session_date, as_of, decision_id, methodology_version`)
equals the result of `latest_entry_qualification_for_instrument_session(instrument_id,
session_date)` at read time — i.e. no strictly newer EQ observation
exists for that instrument/session that would supersede the one this
`EntryActionability` row is bound to. A strict identity-equality
comparison against the freshest real EQ observation, not a looser
Decision-id-only match.

## 16. Session boundary

- `REGULAR` — the only phase in which `EntryActionability` can be
  currently usable.
- `PRE_OPEN` — not yet in scope (mirrors EQ's own `NOT_YET` short-circuit
  one layer down); methodology state should not have been evaluated as
  `ACTIONABLE` here in the first place, since the upstream EQ itself
  would not be `QUALIFIED` in `PRE_OPEN`.
- `CLOSED` — currentness resolves to a non-usable classification (e.g.
  `SESSION_CLOSED`, illustrative label, exact set left to ID-7A) — layer
  3 must not remain currently usable after the session has ended, even
  if the persisted methodology state is still `ACTIONABLE` as historical
  truth.
- `NOT_A_TRADING_SESSION` — `OUT_OF_SCOPE`-equivalent, mirrors EQ.

## 17. Canonical-cycle freshness classification

**`CONDITIONAL_ON_EVIDENCE_AGE`.**

Not a flat "acceptable" (§4's tail — p90–p95 showing 14–19% of daily
range consumed within one cycle's duration, and an 11.68% VWAP-side flip
rate — is real and would be genuinely risky if ignored) and not a flat
"not acceptable" (§4's typical case — median 0.09% absolute move, 88.3%
VWAP-side persistence — shows the architecture is not fundamentally
broken for the common case). The condition is: **Option 1 (canonical-
cycle synchronous) remains sufficient provided the extension/chase gate
(§9) and the evidence-age term of `is_currently_usable` (§14) are real,
substantive, load-bearing gates** — which this methodology now makes
them, grounded in real measured evidence rather than asserted by
assumption. **No ADR-015 revision is required or proposed.**

## 18. ID-7P0 Recommendation-A reassessment

**`A_CONDITIONALLY_ACCEPTED`.**

Distinct from ID-7A0's own `A_CANNOT_BE_DECIDED_UNTIL_ID7B` classification
(that one deferred the question entirely pending this milestone; this one
now answers it). "A — latency compensation only" is accepted, on the
explicit condition that compensation is *active* — a real extension/chase
gate and a real evidence-age term, both frozen in shape by this
methodology (§9, §14) — not merely a passive `LIVE_M5_PROVISIONAL` label
with no behavioral consequence. Direct consequence: ID-7A/ID-7C
implementation must not treat "the checkpoint was QUALIFIED" as
sufficient for `ACTIONABLE` on its own; the extension and freshness gates
are mandatory, not optional refinements.

## 19. UNKNOWN vs NOT_ACTIONABLE

- **`UNKNOWN`** — evidence genuinely missing/uncomputable: no decisive
  completed M5 data, `VWAP_UNAVAILABLE` *and* D1 ATR unavailable
  (invalidation wholly uncomputable), or an evaluation-time error.
  Missing evidence is never interpreted as bearish.
- **`NOT_ACTIONABLE`** — evidence *is* available and the methodology
  evaluated a real condition that failed: upstream Decision not `TRADE`;
  upstream EQ not `QUALIFIED`; entry-location/extension too far (§9);
  session not `REGULAR` at evaluation time.
- **`ACTIONABLE`** — upstream eligible, evidence sufficient, extension
  within tolerance, invalidation computable, reward representation
  produced.

## 20. Reason-code taxonomy (semantic categories, not final names)

`UPSTREAM_DECISION_NOT_TRADE`, `UPSTREAM_EQ_NOT_QUALIFIED` (carrying the
exact upstream EQ state), `INSUFFICIENT_EVIDENCE` (drives `UNKNOWN`),
`ENTRY_TOO_EXTENDED` (§9 gate), `INVALIDATION_UNAVAILABLE` (§10 tier-5
exhaustion), `SESSION_NOT_ACTIONABLE` (§16). Reward/RR is informational
in V0 (§12) and does not by itself produce a distinct reason code.
Currentness-side classifications (§14, e.g. `STALE`/`SUPERSEDED`/
`SESSION_CLOSED`) are a separate, read-time label family — not
persisted reason codes on the methodology-state row.

## 21. VWAP's three distinct roles

Not double-counting a single boolean — three separate purposes on the
same underlying signal:

1. **Qualification evidence** (EQ's own use, unchanged): categorical
   `ABOVE_VWAP`/`BELOW_VWAP`.
2. **Entry-location/extension evidence** (new, ID-7B, §9): the
   quantitative `deviation_pct` magnitude.
3. **Invalidation/risk evidence** (new, ID-7B, §10 tier 1): a VWAP-loss
   crossing event.

## 22. RS / RVOL role

**Not used as an additional gate or hidden vote in V0.** Real magnitude
(`stock_vs_market_pct`, `stock_vs_sector_pct`, `rvol_ratio`) is already
computed and is recorded as explanatory/audit context (already available
at zero additional cost) — but with zero real `(TRADE, QUALIFIED)`
history to check whether magnitude correlates usefully with entry
timing, confidence, or reward persistence, adding it as a gate would be
exactly the "arbitrary extra vote system" the authorization forbids
without evidence support. Deferred, not invented.

## 23. Gap role

**Not incorporated into V0 entry/invalidation/reward methodology.**
`GapContext` has no fill/hold tracking (fixed forever at session open,
§3) and no empirical evidence connects gap size to entry validity, chase
risk, or stop structure for this product. Remains available as
explanatory context only.

## 24. M5 vs M15

**M5 is authoritative for entry trigger, extension, and invalidation
(§8–§10)** — the finest-granularity completed data, directly matching
VWAP's own M5 anchoring. **M15's only role is the trend-agreement input
EQ itself already computed** (§3) — no new, independent M5-vs-M15
precedence or scoring system is invented for ID-7B; the existing
unanimous-agreement rule is reused as-is via the already-`QUALIFIED`
upstream state.

## 25. Completed-candle / provisional-data policy

Every ID-7B input (VWAP, trend, local extrema, OR levels) must use only
completed M5/M15 candles (`is_candle_completed`, §3) — never a
future-looking or still-forming bar. `Quote.last_price` is explicitly
**not** used as entry/VWAP/trend evidence, mirroring EQ's own precedent
exactly. A completed M5 bar within a `REGULAR` (still-open) session still
carries `LIVE_M5_PROVISIONAL` finality (§3) — this is expected and
permitted (§14), not an error.

## 26. Entry-actionability methodology form (gate ordering)

1. Upstream eligibility (§5) → else `NOT_ACTIONABLE`.
2. Evidence sufficiency for evaluation (session `REGULAR`, decisive
   completed M5/VWAP data present) → else `UNKNOWN`.
3. Entry-location & extension validity (§9) → else `NOT_ACTIONABLE`
   (`ENTRY_TOO_EXTENDED`).
4. Invalidation validity (§10) → else `UNKNOWN`
   (`INVALIDATION_UNAVAILABLE`) if genuinely uncomputable.
5. Reward representation (§11–§12, informational).
6. → `ACTIONABLE` / `NOT_ACTIONABLE` / `UNKNOWN`, each with an explicit
   reason code (§20).

Freshness/currentness (dimension B, §14) is **not** part of this
per-evaluation sequence — it is a separate, read-time predicate applied
whenever a consumer asks, reusing `evidence_as_of` captured in step 2–4.

## 27. No score, no ML

No `0–100` score, no weighted confidence, no aggregation of the gates
above into a single number. Deterministic gates only, consistent with
ID-6's own successful approach. No model fitting, no learned threshold,
no optimization against outcomes — this milestone is deterministic
methodology architecture/freeze only.

## 28. Evidence availability audit

Because zero real `(TRADE, QUALIFIED)` episodes exist (§2), availability
cannot be quantified specifically for that intersection. The best
available real evidence is the general population: VWAP/trend are
computed whenever `IntradayAnalyticsEngine` runs with sufficient M5/M15
data (the same inputs EQ itself already relies on in current production,
implying high general availability); OR15 `COMPLETE` 93.25% of the time,
OR30 68.54% (PS-P9B, real 35,232-observation replay, §3); D1 ATR
availability mirrors `TradePlan`'s own existing production reliability
(already in daily use). This is real, but general-population, not
`(TRADE, QUALIFIED)`-specific — flagged honestly rather than presented
as more precise than it is.

## 29. Historical outcome labels (identified, not computed)

Future validation of this methodology (a separately authorized
milestone, not run here) would need: MFE (maximum favorable excursion),
MAE (maximum adverse excursion), time-to-T1, time-to-T2, and
stop-before-target — all identified as future label candidates only. No
fitting/optimization performed.

## 30. Output value-object shapes (conceptual, no source classes)

```
Entry:        { trigger, zone_low, zone_high, basis }
Invalidation: { level, basis }
Reward:       { t1, t2, basis, reward_risk (nullable, informational) }
```

Exact field types/names are ID-7A's to finalize; this freezes the
minimum coherent conceptual shape only.

## 31. Methodology version

A naming convention is frozen — a distinct namespace from
`EntryQualification.methodology_version` and any Decision-side
config/methodology identifier — but **no version string is minted here**.
Minting e.g. `"v1"` would misrepresent this milestone's own
`METHODOLOGY_PARTIALLY_FROZEN` status as a full freeze. A version string
should be minted only once the deferred numeric thresholds (§13) are
resolved.

## 32. Replayability

Every input used (VWAP `deviation_pct`, trend, RS/RVOL magnitudes,
OR `COMPLETE`-only levels, recent completed M5 extrema, D1 ATR,
completed M5/M15 candles) is sourced from persisted, `as_of`-bounded,
market-time-replayable data — no live-only hidden state, no provider
call. Inherits ADR-013's already-documented market-time-only (not
bitemporal/knowledge-time) replay limitation unchanged — not resolved
further here.

## 33. Provider boundary

Zero provider calls. Every query in this milestone was read-only against
`db/athena.db` (`mode=ro`, `PRAGMA query_only=ON`). No live scan, no
artificial production cycle.

## 34. EMR / DarvaX isolation

No EMR threshold/model/label imported. No DarvaX Fibonacci level used or
queried. Both remain untouched by this milestone.

## 35. ID-9 / ID-10 / ID-11 boundaries

Unchanged. `EntryActionability` may expose the invalidation-distance
evidence a future sizing engine (ID-9) would consume, but performs no
allocation. No trailing-stop/ongoing supervision (ID-10) here. No
depth/spread/execution-quality computation (ID-11) here — only an
extension seam is acknowledged, as already frozen by ADR-015.

## 36. Unresolved methodology items (deferred, explicit)

- Extension/chase numeric cutoff, zone width, local-extremum lookback N,
  and any minimum-RR gate — all deferred pending either real
  `(TRADE, QUALIFIED)` evidence accumulation or explicit owner
  risk-tolerance input (§13).
- The upstream EQ long-bias asymmetry (§7) — a real, open, ID-6-owned
  gap this milestone surfaces but does not fix.
- Whether RS/RVOL magnitude, or gap context, ever prove useful once real
  `(TRADE, QUALIFIED)` history exists (§22, §23) — currently deferred,
  not rejected outright.
- Methodology version minting (§31) — deferred until the above resolve.
