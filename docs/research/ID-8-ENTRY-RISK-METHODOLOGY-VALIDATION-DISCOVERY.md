# ID-8 — Entry/Risk Methodology Validation: Discovery + Empirical Contract

Status: **ID-8 DISCOVERY CONTRACT CORRECTED — READY FOR OWNER / CHIEF
ARCHITECT REVIEW** (2026-09-07, target-hit direction wording corrected;
see §54). Not marked closed; methodology not frozen.

## 1. Executive summary

ID-7 (now closed) answers "is this structurally authorized opportunity
actionable now?" ID-8 must answer "given an eligible opportunity, what
entry/risk structure is empirically defensible?" This milestone performs
read-only discovery, defines the exact research contract (observation
unit, entry proxy, forward window, MFE/MAE, target-hit and invalidation
semantics, same-bar-ambiguity policy, outcome taxonomy, statistical
design), and runs one small feasibility sample proving the design is
mechanically sound against real data. It does **not** run the full
historical outcome study, does not tune any threshold, and does not
touch canonical methodology.

Three real findings emerged during discovery that materially shape the
contract:

1. **A large body of directly-relevant empirical work already exists**:
   `docs/research/ID-7B1-RETROSPECTIVE-TRADE-EQ-RECONSTRUCTION.md` §16-20
   already computed MFE/MAE, T1/T2 hit rates and timing, three
   invalidation candidates (VWAP-loss/OR15-boundary/D1-ATR) compared
   head-to-head, and RR distributions on a **783-episode real
   LONG-only cohort**. That work was never packaged as its own milestone
   and its harness/scripts were never committed (`docs/research/ID-7B1-...md`
   §25 — "research script(s)... live under the session scratchpad...
   never under `src/`"), so it must be **re-derived**, not literally
   re-run, but its methodology and numeric findings are directly
   reusable evidence for this contract (§21 below cites them in full).
2. **A fresh, natively-persisted TRADE+QUALIFIED population exists
   today with no replay needed**: 60 real `entry_qualifications` rows
   (`state='QUALIFIED'`, `decision_type='TRADE'`), all from 2026-09-07 —
   the very first real SHORT TRADE decisions in ATHENA's history (§7).
3. **A newly-discovered, real, mechanistic explanation for the
   zero-ACTIONABLE finding**: all 60 of those rows resolved to EA state
   `UNKNOWN`/`INVALIDATION_UNAVAILABLE` — **100%**, no exceptions (§9,
   §18). This sharpens the already-known `LONG_VALIDATED_SHORT_UNVALIDATED`
   limitation into a concrete mechanism, reported honestly as an ID-6/EQ
   methodology observation that ID-8 is not authorized to fix.

No source, schema, methodology, EMR, or DarvaX changes were made.

## 2. Exact scope

In scope: discovery of real data availability; the exact ID-8 empirical
research contract (identity, entry proxy, forward window, formulas,
taxonomy, validation design); a small feasibility sample proving the
contract's mechanics work on real data. Out of scope (explicitly, per
authorization): PositionSizing (ID-9), LivePlanSupervision (ID-10),
execution-quality modeling (ID-11), UI, automated execution, order
placement, any change to `ScoringEngine`/`DecisionEngine`/EntryQualification
methodology/EntryActionability V0 methodology/canonical `Decision`/`TradePlan`,
the full historical outcome study, and any threshold freeze.

## 3. Architecture boundary (preserved)

```
DAILY/STRUCTURAL -> ENTRY QUALIFICATION -> ENTRY ACTIONABILITY -> ID-8 -> ID-9 -> ID-10 -> ID-11
   (WHAT)             (intraday-qualified)     (actionable now)   (entry/risk    (sizing)  (supervision) (execution
                                                                    empirics)                              quality)
```

ID-8 reads downstream of `EntryActionability` (and, for population
breadth, replayed `EntryQualification`) without mutating either. No
downstream execution-plan contract is wired into canonical `TradePlan`
in this milestone.

## 4. Source files inspected

`src/athena/data/id6e_replay_shadow_validation.py`,
`src/athena/data/id7f1_entry_actionability_replay.py`,
`src/athena/data/id6b1_entry_qualification_baseline.py` (`ReadOnlyStore`),
`src/athena/session/engine.py`, `src/athena/session/models.py`,
`src/athena/calendar/engine.py`, `src/athena/domain/market.py`,
`src/athena/data/store/schema.py`, `src/athena/intraday/entry_actionability_models.py`,
`docs/research/ID-7B1-RETROSPECTIVE-TRADE-EQ-RECONSTRUCTION.md`,
`docs/research/ID-7B2-ENTRY-RISK-CALIBRATION-VALIDATION.md`,
`docs/research/ID-7F0-...md`, `docs/research/ID-7F3-...md`.

## 5. Databases/data inspected

`db/athena.db` exclusively, read-only (`mode=ro` + `PRAGMA query_only=ON`
for every query; zero writes; confirmed via `PRAGMA integrity_check` =
`ok`, schema unchanged at 18 before and after this milestone). No
provider/network call was made — all evidence is already-persisted
historical/current data.

## 6. Historical population inventory

| Population | Count | Notes |
|---|---|---|
| Total `decisions` rows | 233,805+ (growing live) | all decision types |
| `TRADE` decisions, LONG | 96,985 | 20 distinct dates, 2026-07-31 → 2026-08-27 |
| `TRADE` decisions, SHORT | 417 | **exactly one date: 2026-09-07 (today)** |
| Distinct (instrument, session) TRADE groups | 5,036 | |
| `entry_qualifications` total rows | 12,214+ | WATCH/TRADE only, persistence began 2026-09-03 |
| `entry_qualifications` state=QUALIFIED | 1,999 | see §7 breakdown |
| `entry_actionabilities` total rows | 1,502+ (growing live) | persistence began ~2026-09-06 (ID-7F2) |
| M5 candle rows | 1,300,236 | 2026-07-23 → 2026-09-07, 33 distinct sessions |

## 7. Exact TRADE population / 8. Exact QUALIFIED population / 9. TRADE+QUALIFIED population

`entry_qualifications` rows with `state='QUALIFIED'`, by `decision_type`
and `session_date`:

| session_date | decision_type | count |
|---|---|---|
| 2026-09-03 | WATCH | 1,104 |
| 2026-09-04 | WATCH | 809 |
| 2026-09-07 | WATCH | 26 |
| 2026-09-07 | **TRADE** | **60** |

The **TRADE+QUALIFIED cohort — the only population structurally eligible
for `EntryActionability` per ID-7A.2's frozen precondition
(`decision_type==TRADE AND entry_qualification_state==QUALIFIED`) — is
exactly 60 rows, all from today, 2026-09-07.** WATCH+QUALIFIED (1,939
rows) is real evidence but architecturally out of ID-8's cohort (WATCH
is never actionable per ADR-015's frozen scope) — noted, not used.

Separately, ID-7B.1's own **replayed** cohort (783 `REPLAYED_QUALIFIED`
LONG episodes, from 6,624 zero-invented-parameter episodes derived from
the 96,985 real LONG TRADE decisions, 20 distinct sessions in the
2026-07-31→2026-08-27 window) remains the only larger-N historical
population — its harness is not committed (§1), so this milestone cites
its already-published numeric findings rather than re-deriving them.

## 10. Direction distribution

All 60 real TRADE+QUALIFIED rows today are **SHORT** (100%). All 783 of
ID-7B.1's replayed QUALIFIED episodes are **LONG** (100%) — confirmed
independently in that report's §9. **No overlapping LONG+SHORT
QUALIFIED population exists at any point in ATHENA's history to date.**
Zero SHORT decisions of any kind existed before 2026-09-07 (ID-7B.1 §9,
independently reconfirmed here via a fresh direction-by-date query).

## 11. Session distribution

TRADE+QUALIFIED (native): 1 session (2026-09-07). Replayed QUALIFIED
(ID-7B.1): 20 sessions. Combined, real TRADE-decision activity now spans
21 distinct sessions total (one more than ID-7B.1's own snapshot,
reflecting today's session).

## 12. M5 forward-data coverage

1,300,236 M5 rows across 33 sessions, 2026-07-23→2026-09-07. Bar density
per session is real and irregular (not a clean fixed 75 bars/day) —
sampled one liquid instrument (NSE:RELIANCE) across 8 recent sessions:
52–135 M5 bars/session. For this milestone's own feasibility cohort
(§20), every one of the 60 checkpoints had a real entry candle **and**
at least one forward candle (0 skips of either kind — see §20); median
30 forward M5 bars available per checkpoint (today's session was
roughly half-elapsed at query time).

## 13. VWAP reconstructability

Fully reconstructable using the exact same bounded pattern ID-7E's
production stage and ID-7F1's replay already use (`IndicatorEngine.compute`
over `completed_candles`) — no new formula needed for the checkpoint's
own VWAP. **Forward/rolling VWAP recomputation for a post-entry window is
new** (existing code only computes VWAP as-of one checkpoint).

## 14. OR15 coverage

Already characterized on the comparable target-cohort by ID-7B.1 §12:
778/783 (99.36%) `COMPLETE`. No new query run here; cited as
representative of session-time-of-checkpoint-dependent availability.

## 15. Available future horizon

Same-session only, bounded by `session_open_close_ts(ctx, session_date, tzinfo)`
(`src/athena/session/engine.py:94-115`, taking a `CalendarContext` from
`CalendarEngine.context_for(d)` — `src/athena/calendar/engine.py:109` — and
returning `(open_ts, close_ts)` from the calendar's own day-specific
`close_time`, never a hardcoded 15:30). No overnight extension is
proposed or needed — every checkpoint in both the native and replayed
cohorts had substantial same-session forward data (§12).

## 16. Costs/slippage availability

**Confirmed `NOT_AVAILABLE`.** Full schema scan (30 tables) found zero
spread/bid/ask/slippage/commission/brokerage/STT/fee columns anywhere.
`quotes` carries only `(instrument_id, ts, last_price, volume, source)` —
last-traded-price snapshots, no execution-realism signal. A
`trade_outcomes` table exists (`outcome_id, decision_ref, entry_price,
exit_price, quantity, pnl, holding_seconds, adherence_json, closed_ts`)
but holds **exactly 1 row** — negligible, not usable as an evidence
source. ID-8 must therefore separate `RAW_PRICE_PATH_VALIDATION` from
`NET_EXECUTION_PROFITABILITY` (§25) and never use the word "profitable."

## 17. Observation-unit alternatives

- **(a) Every eligible checkpoint, independently.** Maximum information,
  but repeated same-symbol/session checkpoints are not independent
  draws — must be paired with session-grouped (never per-observation)
  statistical treatment.
- **(b) First eligible checkpoint per (instrument, session) only**
  (ID-7B.1's own choice for its primary cohort). Avoids over-weighting
  heavily-churned symbols; loses information about later-in-session
  re-qualification behavior.
- **(c) One observation per continuous qualification episode**
  (ID-7B.1's "episode" construction: consecutive-in-time same-`decision_type`
  runs, boundary on any type change or session-date change — zero
  invented time-gap threshold).
- **(d) Every checkpoint, but only the first is used for "does it ever
  qualify" style questions while later re-checks feed re-entry-after-
  invalidation questions separately.**

## 18. Recommended observation identity

**Adopt (c) — episode-first-checkpoint — as the primary V0 research
unit**, reusing ID-7B.1's exact zero-invented-parameter boundary rule
(instrument+session, consecutive-same-`decision_type` run, break on any
type change or date change). Rationale: it is the only alternative
already proven at scale (6,624 episodes, independently re-derived twice
in ID-7B.1, exact accounting match), it avoids the over-weighting bias
of (a), and it captures the natural entry-timing-relevant instant (the
moment an opportunity *first* becomes eligible) without inventing a new
rule. The full observation-level (every checkpoint) reconstruction
remains a legitimate, lower-priority supplementary pass for a future
continuation, exactly as ID-7B.1 itself flagged (§22 of that report) —
not required to close this contract.

Repeated-checkpoint policy: within an episode, only the **first**
checkpoint is the primary observation; later checkpoints in the same
episode are descriptive-only (available for a future re-entry-after-
invalidation study, not counted twice in the primary population).

## 19. Entry-proxy alternatives / 20. Recommended entry proxy

Alternatives: (a) frozen ID-7 checkpoint-close (theoretical, no fill
assumption); (b) next completed M5 open as an execution proxy; (c) next
M5 close. **Recommend (a), explicitly labeled a research proxy, not an
execution assumption** — this is what ID-7's own frozen `EntryReference`
already uses, keeping ID-8 evidence directly comparable to already-
published ID-7B/ID-7B.1/ID-7B.2 figures, and no execution-cost data
exists (§16) to make (b)/(c) any more "realistic" in a cost-aware sense
today. This must be stated explicitly in every ID-8 output as
`ENTRY_PROXY = CHECKPOINT_CLOSE_THEORETICAL`, never implied as a
guaranteed fill.

**Feasibility proof (§26):** entry price was successfully extracted for
60/60 real checkpoints via "the latest completed M5 candle at or before
`as_of`" — 0 misses.

## 21. Forward-window contract

`session_day_start(as_of, tzinfo)` for the lower reference (unused
directly for forward — kept only as the existing backward-bound
precedent); forward window = every M5 candle for the same instrument
with `substr(ts_open,1,10) = session_date AND ts_open > entry_checkpoint`,
bounded above only implicitly by the session's own data (no candle rows
exist past `session_open_close_ts`'s close in practice, but a defensive
upper-bound filter against `close_ts` should be added in the full
implementation for explicitness, per §17 of ID-7B.1's own precedent: a
direct SQL date/time filter, never a row-count `LIMIT`, so a forward
window can never silently leak into the next session).

## 22. MFE formula / 23. MAE formula

Direction-aware, computed against every forward candle's `high`/`low`
(never `close`-only, to capture intrabar reachability — see §25):

- LONG: `MFE = max((candle.high − entry) / entry)` across the window;
  `MAE = max((entry − candle.low) / entry)`.
- SHORT: `MFE = max((entry − candle.low) / entry)`;
  `MAE = max((candle.high − entry) / entry)`.

Both are running maxima over the whole forward window (not a single
final value) — proven mechanically in §26 (median MFE 0.61%, median MAE
0.63% on the 60-row feasibility sample).

## 24. Intrabar-touch semantics / 25. Close-confirmed semantics

**Corrected 2026-09-07 (Owner source review) — the original text below
had LONG/SHORT reversed; see §54 for the correction record.**

`INTRABAR_TOUCH`, direction-signed and target-specific (an upside LONG
target vs. a downside SHORT target are barriers on opposite sides of
entry, so the triggering OHLC field is necessarily different for each):

- LONG target (upside): `INTRABAR_TOUCH` iff `candle.high >= target_price`.
- SHORT target (downside): `INTRABAR_TOUCH` iff `candle.low <= target_price`.

`CLOSE_CONFIRMED`, same direction convention:

- LONG target: `candle.close >= target_price`.
- SHORT target: `candle.close <= target_price`.

**Report both** where implemented (ID-7B.1 already reports intrabar-
touch-based hit rates in §16/§18; this milestone's feasibility sample
also uses intrabar touch for T1/T2, §26) — they answer different
questions (reachability vs. confirmed follow-through) and neither
should be silently treated as a guaranteed executable fill (§16, §20).

## 26. T1 definition / 27. T2 definition

T1/T2 remain exactly the frozen ID-7A `T1_GOAL_BAND_PCT`/`T2_GOAL_BAND_PCT`
values, reused unchanged, not re-derived or re-tuned, and unaffected by
this correction (the percentages were never in question — only the
touch-direction wording was):

- LONG: `T1 = entry × 1.01`, `T2 = entry × 1.015`.
- SHORT: `T1 = entry × 0.99`, `T2 = entry × 0.985`.

Hit = first forward candle satisfying §24's `INTRABAR_TOUCH` rule for
that target and direction (i.e. `candle.high >= T1/T2` for LONG,
`candle.low <= T1/T2` for SHORT); `time_to_hit` = minutes from the entry
checkpoint's own completion instant to that candle's own completion
instant.

## 28. VWAP-loss definition

Subsequent completed-M5 close crossing to the losing side of the
checkpoint's own session VWAP (LONG: close falls back below VWAP;
SHORT: close rises back above VWAP) — the exact frozen ID-7 V0 operative
invalidation concept (ID-7B.2 §"VWAP-loss validated primary
invalidation"), applied forward instead of only as a static checkpoint
reading. **Not implemented in this milestone's feasibility sample**
(§26) because the sample's only available real cohort had `VWAP-based
risk geometry already invalid at entry` (§9/§18) — computing a
forward VWAP-loss crossing against an already-wrong-side VWAP would
produce a meaningless (already-triggered-at-t=0) result. A future
continuation with a valid-geometry cohort (LONG, or a future genuinely
valid SHORT population) is required to exercise this formula end-to-end.

## 29. Initial risk-distance definition / 30. RR-to-T1 / 31. RR-to-T2

`risk_distance_pct = |entry − VWAP| / entry` at the checkpoint (only
defined when risk geometry is valid, i.e. `INVALIDATION_UNAVAILABLE` did
not fire); `RR_to_T1 = (1%) / risk_distance_pct`; `RR_to_T2 = (1.5%) /
risk_distance_pct` — both informational only, per ID-7C's own
`RR_INFORMATIONAL_ONLY` verdict, never a gate. ID-7B.1 §19 already
computed representative medians on its LONG cohort (`M5_CLOSE vs
VWAP_LOSS` RR-to-T1 median 2.19) — cited as prior evidence, not
re-derived here.

## 32. Same-bar ambiguity policy

**Tightened 2026-09-07 (Owner source review) — see §54 for the
correction record.** The original text below treated the target and the
operative invalidation as two symmetric intrabar HIGH/LOW barriers and
therefore over-flagged ambiguity. The actual frozen pair is **not**
symmetric: target-hit is `INTRABAR_TOUCH` (§24, triggered by `high`/`low`,
i.e. reachable at any instant within the bar), while VWAP-loss is
**`CLOSE_CONFIRMED` only** (ID-7B.2's own frozen definition — a
subsequent *completed*-M5 close on the losing side of VWAP; there is no
intrabar VWAP-loss concept in the frozen V0 contract). This asymmetry
has a direct consequence for ordering:

**Reasoned resolution:** VWAP-loss's own definition anchors its
occurrence to the candle's *close* — necessarily the last instant
covered by that candle. An intrabar target touch (`high`/`low`) can only
occur at or before that same instant — **including exactly at the
closing print itself** (a target could theoretically first become true
at the same instant the bar closes, in which case target and
invalidation are simultaneous, not sequential). The provable relation is
therefore **not** "target strictly before invalidation" — it is:

**`TARGET_NO_LATER_THAN_INVALIDATION`** — whenever a single forward M5
candle satisfies both the target's `INTRABAR_TOUCH` condition and
VWAP-loss's `CLOSE_CONFIRMED` condition, the target event is proven to
occur **at or before** (never strictly after) the VWAP-loss instant
within that bar. This is not an assumption that target wins by default;
it follows directly from VWAP-loss being defined as a close-only event.
No real ordering ambiguity exists for this specific pairing — OHLC data
does not need to (and cannot) resolve anything finer than "at or before"
here, and the contract must not overstate that resolution as strict
precedence.

**Consequence for the contract: `AMBIGUOUS_SAME_BAR` does not apply to
target-vs-VWAP-loss comparisons at all**, under the frozen semantics —
that same-bar case is always classifiable as
`TARGET_NO_LATER_THAN_INVALIDATION`, never "undetermined." `AMBIGUOUS_SAME_BAR`
remains a live, necessary category **only for comparisons between two
genuinely intrabar-reachable barriers** (e.g. a future candidate
invalidation modeled as an intrabar level, such as OR15-boundary — ID-7B.1
§18's own comparison set — if a future milestone treats OR15-boundary as
an intrabar rather than close-confirmed trigger; that determination is
not made here and remains a future question). For any such genuinely
symmetric intrabar-vs-intrabar pairing, the original rule still holds:
if a single candle's `[low, high]` range satisfies both barriers, the
event ordering is undetermined from OHLC data alone — classify it
`AMBIGUOUS_SAME_BAR`, exclude it from any ordered "X-before-Y" claim,
and still count it toward reachability-only statistics for each barrier
individually. Never optimistically assume either side wins by default
for a genuinely symmetric pairing — only for the specific intrabar-vs-
close-confirmed asymmetry proven above does an `AT_OR_BEFORE` (not
strictly-before) relation exist.

**Do not manufacture ambiguity where the event semantics already
establish an at-or-before relation** — this correction exists precisely
to prevent that, and precisely to avoid overstating it as strict
sequencing.

## 33. Outcome taxonomy

**Corrected 2026-09-07 (Owner source review) — see §54.** The original
taxonomy listed `TARGET_1_FIRST`/`TARGET_2_FIRST` as if they were two
competing terminal states, which is logically inconsistent with the
already-stated fact that reaching T2 necessarily traverses T1 on a
continuous price path (T1 and T2 are not mutually exclusive alternatives
— T2 being reached implies T1 was already reachable). The taxonomy is
now split into two genuinely separate concepts, never conflated:

**(A) Target reachability metrics** — tracked independently for each
goal band, not as a single "first target" pick:

- `T1_INTRABAR_REACHED` / `T1_CLOSE_CONFIRMED` (boolean, plus first-hit
  timestamp, bar count, and minutes-to-hit for each).
- `T2_INTRABAR_REACHED` / `T2_CLOSE_CONFIRMED` (same fields). T1 is the
  first frozen goal-band threshold relevant to the target-vs-invalidation
  terminal question below; T2 is an additional reachability/follow-through
  outcome, never a competing "first target" terminal state.

**(B) First-terminal-ordering outcome** — the single execution/risk
question ("did the target side or the invalidation happen first,
relative to T1"), one mutually-exclusive label per observation:

- `TARGET_SIDE_NO_LATER_THAN_INVALIDATION` — T1 was reached
  (`INTRABAR_TOUCH`) strictly before the forward window's first
  `CLOSE_CONFIRMED` VWAP-loss bar, **or** both occur on the same bar (per
  §32's `TARGET_NO_LATER_THAN_INVALIDATION` relation — same-bar cases are
  classified here, never as `AMBIGUOUS_SAME_BAR`, since that relation is
  always resolvable to "no later than").
- `INVALIDATION_FIRST` — a `CLOSE_CONFIRMED` VWAP-loss bar occurs before
  T1 was ever reached.
- `SESSION_END_NO_RESOLUTION` — neither T1 nor VWAP-loss occurs by the
  last available same-session candle.
- `INSUFFICIENT_FORWARD_DATA` — zero forward candles exist at all (a
  data-availability defect, §36; 0 occurrences in §46's sample — 60/60
  reconstructed).

`AMBIGUOUS_SAME_BAR` is **not** a label in (B) — per §32, it is
structurally unreachable for the target-vs-VWAP-loss pairing and is
reserved exclusively for a genuine future intrabar-vs-intrabar
invalidation-candidate comparison, tracked separately from this
taxonomy if and when such a candidate is added. No profitability
semantics are introduced by any of the above — every label describes
raw price-path ordering only (§16).

## 34. Time-to-event semantics

Minutes elapsed from the entry checkpoint's own **completion instant**
(`entry_ts_open + 5min`, matching `session.engine.is_candle_completed`'s
own definition — never the raw `ts_open`) to the target/invalidation
candle's own completion instant. Bar-count distance is reported
alongside minutes for readability, never used as the sole unit (bar gaps
are real and irregular, §12).

## 35. Session-end handling

A checkpoint with no forward bar reaching any labeled event by the last
available same-session candle is `SESSION_END_NO_RESOLUTION` — not
`INSUFFICIENT_FORWARD_DATA` (that label is reserved for a checkpoint
with **zero** forward candles at all, a data-availability defect, never
observed in §26's sample).

## 36. Insufficient-forward-data handling

See §35 — reserved for genuine data gaps (e.g. a symbol delisted or
ingestion-missing mid-session). Not observed in the feasibility sample;
must be tracked as its own defect-style category (mirroring ID-7F1's
own `PIT_EVIDENCE_DEFECT`/`DATA_AVAILABILITY` distinction) in any
full-scale run, never silently dropped from the denominator.

## 37. Candidate descriptive context variables

Direction, session-time-of-checkpoint bucket, market regime, RS
(`stock_vs_market_pct` quartile), RVOL (`rvol_ratio` quartile), VWAP
deviation at entry, OR15 context, initial risk-distance bucket — ID-7B.1
§20 already found a real, monotonic-ish RS/RVOL association with T1 hit
rate on its LONG cohort (Q1 16.33% → Q4 33.16% for RS;
Q2 17.86% → Q4 31.12% for RVOL) worth citing as a candidate-promotion
signal for a **future** milestone, explicitly not fit or gated here.
Dimensionality must stay controlled — no combinatorial threshold search
(§17 of the authorization).

## 38. Direction-handling policy

**Report LONG and SHORT populations completely separately; never pool.**
Today's evidence is LONG-only for the large replayed cohort and
SHORT-only for the native cohort — there is currently no overlapping
population to even test comparability on. `LONG_VALIDATED_SHORT_UNVALIDATED`
is preserved and, per §9/§18's fresh finding, is now understood more
precisely: the EQ v0 "QUALIFIED" criterion is bullish-shaped
(VWAP-positive AND BULLISH trend), so a SHORT Decision that happens to
receive a QUALIFIED EQ verdict inherits an entry-side VWAP relation that
is structurally the wrong side for a SHORT's own risk geometry — this is
why **100% of today's 60 real SHORT TRADE+QUALIFIED checkpoints**
resolved to `UNKNOWN`/`INVALIDATION_UNAVAILABLE`, never `ACTIONABLE`.
This is an ID-6/EQ methodology observation, reported honestly; **ID-8
does not propose or make any ID-6 change** — it is out of this
milestone's authorized boundary.

## 39. Chronological validation design / 40. Session-grouping policy

No random per-observation split, ever. Reuse ID-7B.1's own already-
executed discipline (§10 of that report): group by session, never split
individual observations within a session. Given only 20-21 distinct
sessions carry any real TRADE-decision activity today, a single fixed
discovery/validation split (as ID-7B.2 used, 14/6) would leave a small
validation set; **recommend a leave-some-sessions-out or session-level
cross-validation style design** for any future full-scale ID-8
calibration, exactly as ID-7B.1 itself already recommended (its own
§10) — not decided or executed here (no threshold fitting occurs in
this milestone at all).

## 41. Uncertainty/reporting approach

Every future full-scale statistic must carry its own N and event count
alongside the point estimate (as ID-7B.1's own tables already do); no
session-independent confidence interval should be computed given the
real serial-correlation risk within a session — a future continuation
should consider session-cluster-aware or session-block-bootstrap
intervals rather than naive per-observation CIs.

## 42. Existing infrastructure reusable as-is

`ReadOnlyStore` (`mode=ro`+`query_only=ON`), `session_day_start`,
`completed_candles`/`latest_completed_candle`, `IndicatorEngine.compute`
(VWAP), `OpeningRangeEngine.assess`, `SessionContextEngine.assess`,
`CalendarEngine.context_for`/`session_open_close_ts`, the exact
composite-identity/binding-validation pattern from ID-7F1/ID-7F3, and
ID-7B.1's own leak-safe forward-window SQL predicate (`substr(ts_open,1,10)=
session_date AND ts_open>checkpoint_ts`, direct filter, never `LIMIT`).

## 43. Infrastructure requiring small extension

None of the existing backward-bounded `ReadOnlyStore` methods need
modification — a **new**, separate forward-reading function (mirroring
`candles(...)`'s own shape but with a `>` lower bound and no upper bound
beyond the session) is the only small addition needed; it should live
alongside, not inside, the existing backward-only helpers to keep the
"never forward-looking" invariant grep-provable for every existing
consumer (a dedicated source-scan test, mirroring ID-7F1's own zero-
provider-call proof, should confirm no backward-replay code path
imports the new forward helper).

## 44. Data unavailable/unsupported

Spread/bid-ask/slippage/commission/fees (§16); a real overlapping
LONG+SHORT QUALIFIED comparison population (§10); a real valid-geometry
SHORT population to exercise VWAP-loss forward-invalidation timing
end-to-end (§28); a non-QUALIFIED TRADE comparison population for
outcome contrast (flagged, unresolved, by ID-7B.1 itself, §22 of that
report — still unresolved here, deferred).

## 45. Bias/leakage risks

Episode-first-checkpoint selection (§18) systematically under-samples
heavily-churned symbols' later-session behavior — flagged, not fixed.
Forward-window SQL must never use `LIMIT` (leakage risk into next
session) — proven safe in §26's implementation (direct date/timestamp
filter only). Entry-proxy is theoretical, not fill-realistic (§20) —
every output must say so explicitly. `config_snapshot_id` stratification
(ID-7B.1 §21: `cfg-full-validation`'s qualified rate is ~10x lower than
`cfg-host-ops`) means pooling across config-snapshot paths without
noting this could distort any full-scale future rate estimate.

## 46. Feasibility replay/sample results

**Correction note (2026-09-07, Owner source review — see §54):** the
feasibility calculation's own code used `low_d <= target_price` for the
SHORT target and `high_d >= target_price` for the LONG target throughout
— i.e. it already matched §24's corrected rule exactly (all 60 rows in
this sample are SHORT, so the code path exercised was `candle.low <=
target_price`, the correct downside-target intrabar test). **Only this
report's prose description of that rule (§26/27, old text) was reversed
— the calculation itself was never wrong, and none of the numbers below
have changed.** The same-bar-ambiguity check this sample ran used a
generic symmetric adverse-price probe (a placeholder, never real
VWAP-loss — VWAP-based invalidation could not be exercised on this
cohort at all, see below), which is now superseded by §32's corrected
policy: since VWAP-loss is close-confirmed-only, a genuine
target-vs-VWAP-loss same-bar ambiguity is not possible under the frozen
semantics regardless of what any adverse-price probe reports. The "0
ambiguous occurrences" this sample found is therefore not read as
evidence about a real ambiguity rate (it never could have been, given
this cohort could not exercise VWAP-loss at all) — it remains only a
proof that the detection mechanism itself runs without error, retained
for that narrow purpose only.

Read-only, against the real live `db/athena.db`, zero writes, zero
provider calls. Population: all 60 real, currently-persisted
TRADE+QUALIFIED `entry_qualifications` rows (2026-09-07, 100% SHORT,
§9). For each: extracted the entry-proxy price (§20), built the forward
window (§21), computed MFE/MAE (§22/§23), T1/T2 intrabar-touch hit and
time-to-hit (§26/§27, using the corrected — and, as confirmed above,
originally-correctly-coded — downside-target rule), and ran the
placeholder same-bar-ambiguity check described above.

**Result (unchanged by this correction): 60/60 reconstructed (100%), 0
skipped for a missing entry candle, 0 skipped for missing forward
data.** T1 (+1%) hit rate 21/60 = 35.0% (median time-to-hit 34.0 min);
T2 (+1.5%) hit rate 8/60 = 13.3%; median MFE 0.61%, median MAE 0.63%;
median 30 forward M5 bars available per checkpoint.

**These hit-rate numbers must NOT be read as methodology-validating
evidence** — this is a single-session, SHORT-only, small-N (60)
mechanical proof, and (§9/§18) every one of these 60 checkpoints already
carries an invalid VWAP-based risk geometry (`INVALIDATION_UNAVAILABLE`,
60/60), so the invalidation leg of the contract (§28) could not be
exercised at all on this batch. What this feasibility run **does**
prove: the entry-proxy extraction, leak-safe forward-window read,
direction-aware MFE/MAE, and correctly-directed intrabar target-touch
detection all work end-to-end against real data — the mechanical bar
this milestone was asked to clear (§23 of the authorization). **It
remains `MECHANICAL_RECONSTRUCTION_PROOF` only**, not a methodology
validation of any kind, and its 0-ambiguous-occurrences figure carries
no evidentiary weight about a real target-vs-VWAP-loss ambiguity rate
(there is no such rate to measure under the frozen semantics — §32).

## 47. Production-write/provider-call confirmation

Zero. Every query used `mode=ro` + `PRAGMA query_only=ON`; `PRAGMA
integrity_check` = `ok` and `schema_version` = 18 confirmed unchanged
before and after this milestone; no `save_*` method was called; no
market-data provider was invoked (all evidence already persisted).

## 48. EMR isolation

`db/emr.db`, `config/emr/operational.json` not read or referenced by
this milestone at all.

## 49. DarvaX isolation

`darvax/`, `config/darvax.json` not read or referenced by this
milestone at all.

## 50. Proposed ID-8 methodology-validation contract (summary)

- Observation unit: episode-first-checkpoint (§18).
- Entry proxy: checkpoint-close, explicitly theoretical (§20).
- Forward window: same-session, direct-filter-bounded, no `LIMIT` (§21).
- MFE/MAE: direction-aware running-max over candle high/low (§22-23).
- Target hit: intrabar-touch primary (`high>=target` LONG, `low<=target`
  SHORT — corrected direction, §24), close-confirmed reported alongside
  (§25); T1/T2 = frozen ID-7 ±1%/±1.5% bands, unchanged (§26-27).
- Invalidation: forward VWAP-loss crossing, direction-aware,
  close-confirmed only (§28) — not yet exercised end-to-end (no
  valid-geometry cohort available today).
- Same-bar ambiguity: `AMBIGUOUS_SAME_BAR` classification for genuinely
  symmetric intrabar-vs-intrabar barrier pairs only — **structurally
  inapplicable to target-vs-VWAP-loss**, since that pairing always
  resolves to `TARGET_NO_LATER_THAN_INVALIDATION` (at-or-before, never
  strictly-before) rather than an unresolved ordering (§32).
- Outcome taxonomy: two separated concepts — (A) 4 independent target-
  reachability metrics (T1/T2 × intrabar/close-confirmed), never a
  competing "first target" pick; (B) 4 mutually-exclusive first-terminal-
  ordering labels (`TARGET_SIDE_NO_LATER_THAN_INVALIDATION`/
  `INVALIDATION_FIRST`/`SESSION_END_NO_RESOLUTION`/
  `INSUFFICIENT_FORWARD_DATA`) (§33).
- Statistical design: session-grouped, chronological, no random split,
  leave-some-sessions-out recommended for the next full-scale pass
  (§39-41).
- LONG/SHORT reported separately, never pooled (§38).
- Cost-aware profitability claims explicitly out of scope; only
  `RAW_PRICE_PATH_VALIDATION` language permitted (§16, §46).

## 51. Owner decisions genuinely required

1. Whether to authorize a full-scale ID-8 continuation that **rebuilds**
   (not reuses — nothing was committed) a replay harness over the
   783-episode LONG cohort plus native TRADE+QUALIFIED rows as they
   accumulate, to actually execute the outcome taxonomy/statistics at
   scale.
2. Whether the forward-VWAP-loss invalidation leg (§28) should be
   exercised on ID-7B.1's LONG replayed cohort specifically (the only
   population with valid entry risk-geometry today), since the native
   SHORT population cannot exercise it (§9/§18/§46).
3. Whether the newly-sharpened EQ SHORT-geometry finding (§38) warrants
   a separate, explicitly-scoped ID-6-track investigation (outside
   ID-8's own boundary) — recommendation only, no action taken here.

## 52. Recommended next implementation/research step (recommendation only)

A follow-on ID-8.x milestone that (a) rebuilds a small, committed,
reusable forward-window module (mirroring §43's design) inside
`src/athena/data/`, (b) re-derives ID-7B.1's 783-episode LONG cohort via
a fresh replay (since the original harness was never committed) to
exercise the full contract including VWAP-loss invalidation timing
end-to-end, and (c) begins accumulating a genuine SHORT comparison
population naturally as production continues — without inventing a
minimum-session threshold, mirroring ID-6E/EM-7D0's own precedent of
accepting "operationally sound, not yet statistically ready" as an
honest interim classification if evidence remains thin.

## 53. Files changed

Created: this report only. Zero source/schema/config changes.
`git diff --check` clean; `git status --short` scoped to this file plus
the standard tracking-doc updates. PID 2453, schema (18), and every
persisted row remain untouched throughout.

## 54. Correction record (2026-09-07, Owner source review)

**Defect found:** §26/27's original prose stated target-hit used
`low` for the LONG target and `high` for the SHORT target — reversed.
An upside LONG target must be tested against `candle.high`; a downside
SHORT target against `candle.low`.

**Scope of the defect: documentation-only.** The feasibility
calculation's own code (§46) already implemented the correct rule
(`low_d <= target_price` for the SHORT-target branch, `high_d >=
target_price` for the LONG-target branch) — every one of the 60
feasibility rows is SHORT, so the code path actually exercised was
already correct. **No feasibility numbers changed**: T1 hit rate 21/60
(35.0%), T2 hit rate 8/60 (13.3%), median MFE 0.61%, median MAE 0.63%,
60/60 reconstructed — all unchanged from the original run.

**Corrections applied:**
- §24/25: explicit, direction-signed `INTRABAR_TOUCH`/`CLOSE_CONFIRMED`
  formulas for both LONG and SHORT:

  ```
  INTRABAR_TOUCH:
    LONG  -> candle.high >= target_price
    SHORT -> candle.low  <= target_price

  CLOSE_CONFIRMED:
    LONG  -> candle.close >= target_price
    SHORT -> candle.close <= target_price
  ```
- §26/27: corrected touch-direction wording; T1/T2 percentages
  themselves were never wrong and are restated unchanged
  (LONG ×1.01/×1.015, SHORT ×0.99/×0.985).
- §32: tightened the same-bar-ambiguity policy. Because VWAP-loss is
  `CLOSE_CONFIRMED`-only (never intrabar) while target-hit is
  `INTRABAR_TOUCH`, a target touch within a bar can never occur *after*
  that same bar's own close — so a bar satisfying both conditions has a
  deterministic order (target at-or-before invalidation), never a real
  ambiguity. `AMBIGUOUS_SAME_BAR` is therefore **inapplicable to
  target-vs-VWAP-loss** and remains reserved for a genuine future
  intrabar-vs-intrabar barrier pairing only.
- §33, §46, §50: cross-references updated for consistency with the
  above; MFE/MAE formulas (§22/23) were independently re-checked against
  the corrected rule and found already correct — no change needed there.

**60/60 real SHORT TRADE+QUALIFIED → `UNKNOWN`/`INVALIDATION_UNAVAILABLE`
finding: unchanged, unaffected by this correction** (§9/§18) — it
concerns upstream EQ/EntryActionability risk-geometry evaluation, not
this report's own forward-analysis contract. `LONG_VALIDATED_SHORT_UNVALIDATED`
remains unchanged; no ID-6/EQ methodology touched.

**Safety:** read-only against `db/athena.db` throughout this correction
(no rerun of the feasibility sample was needed, since its code was
already correct); `schema_version` confirmed unchanged at 18,
`integrity_check: ok`; PID 2453 untouched; zero provider/network calls;
zero EMR/DarvaX touch. `git diff --check` clean — diff scoped to this
report file only (no tracking-doc changes required for a documentation
correction with unchanged numeric results).

**Recommended next step (recommendation only):** proceed to Owner
decision on §51's three open questions; no further correction identified
in this pass.

---

**ID-8 DISCOVERY CONTRACT CORRECTED — READY FOR OWNER / CHIEF ARCHITECT
REVIEW.**
