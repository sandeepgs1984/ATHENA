# ATHENA Portfolio Sync - PS-P9B Opening-Range Setup Methodology Replay

**Date:** 2026-09-04
**Branch:** `feature/portfolio-sync`
**Milestone:** PS-P9B - methodology/research only
**Status:** Ready for Owner / Chief Architect review

---

## 1. Executive Summary

PS-P9B asked whether ATHENA's approved Opening Range evidence can be promoted
from deterministic measurement into a trustworthy owner-facing Portfolio Setup
semantic without inventing thresholds or unstable session labels.

Verdict: not yet for production.

The evidence is real and deterministic, but raw Opening Range events are too
directional, transient, and conflict-prone to expose as a single owner-facing
Setup label without more owner decisions. Replay found frequent upside and
downside events, many returned-inside-range cases, and real OR15/OR30 conflicts.
Production Portfolio Setup should remain null/deferred under
`portfolio-interpretation-v2`.

Recommended next step: freeze a small PS-P9C methodology decision, not code, if
the owner wants to continue. The safest candidate is directional structural
Setup only, with `BREAKOUT`, `BREAKDOWN`, and null considered separately from
Status/Action. If the owner does not want downside labels in My Portfolio, keep
Setup deferred.

## 2. Frozen PS-P9A Owner Decisions

PS-P9A is Owner / Chief Architect approved and frozen 2026-09-04.

Frozen semantics:

- Setup means a current, observable structural/actionability pattern supported
  by coherent ATHENA evidence.
- Setup does not mean D1 Trend, Status, Next Action, Conviction, P&L, TradePlan
  existence, EntryQualification result, or generic bullish/bearish opinion.
- Trend and Setup are independent dimensions.
- EntryQualification is context/confirmation only; `QUALIFIED` must not map
  directly to `BREAKOUT`.
- TradePlan is level/action context only; entry band, stop, and target cannot be
  converted into setup labels.
- DarvaX, EMR, and other satellite/research artifacts remain excluded.

## 3. Exact Opening Range Evidence Contract

Approved source artifacts:

- `OpeningRangeWindow`: `OR15`, `OR30`.
- `OpeningRangeFormationStatus`: `FORMING`, `COMPLETE`, `INCOMPLETE_DATA`,
  `NOT_AVAILABLE`, `NOT_APPLICABLE`.
- `OpeningRangeRelation`: `ABOVE_RANGE`, `BELOW_RANGE`, `INSIDE_RANGE`,
  `AT_HIGH`, `AT_LOW`, `UNAVAILABLE`.
- `BreakoutEvent`: `UPSIDE_BREAKOUT_EVENT`, `DOWNSIDE_BREAKDOWN_EVENT`,
  `NO_EVENT`, `NOT_OBSERVED`.

The implementation is measurement-only. It does not define BUY/SELL, strength,
failure, entry, stop, target, confirmation, or trade meaning.

## 4. OR15 Semantics

OR15 is the first 15 minutes of the regular session, derived from
`SessionContext.session_open_ts` and completed canonical M5 candles only. A
normal session expects three M5 bars. OR15 becomes usable only when the window
has elapsed and all expected canonical slots are present.

Replay: OR15 was `COMPLETE` in 32,853 / 35,232 observations (93.25%) and
`INCOMPLETE_DATA` in 2,379 (6.75%).

## 5. OR30 Semantics

OR30 is the first 30 minutes of the same regular session and expects six normal
M5 bars. It is parallel evidence, not superior or inferior to OR15 in existing
approved methodology.

Replay: OR30 was `COMPLETE` in 24,147 / 35,232 observations (68.54%),
`FORMING` in 5,304 (15.05%), and `INCOMPLETE_DATA` in 5,781 (16.41%).

## 6. Directionality Analysis

Direction is not optional. The approved event vocabulary distinguishes upside
breakout from downside breakdown. Collapsing both into `BREAKOUT` would destroy
meaning.

Replay:

- OR15 upside: 6,126 (17.39%).
- OR15 downside: 9,216 (26.16%).
- OR30 upside: 3,777 (10.72%).
- OR30 downside: 6,142 (17.43%).
- Any OR event: 15,342 observations.
- Same observation containing one window upside and the other downside: 524.

Recommendation: do not use a generic directionless `BREAKOUT` for all OR
events.

## 7. Upside Breakout Semantics

Upside OR breakout is supportable as a deterministic measurement. It is not yet
supportable as a production Setup label because lifecycle and OR15/OR30
precedence are not frozen.

Replay:

- OR15 upside only or with other states: 6,126 observations.
- OR30 upside only or with other states: 3,777 observations.
- OR15 and OR30 both upside: 3,541 observations.
- OR15 upside but OR30 no event: 1,076 observations.

Recommendation: if owner-facing Setup is pursued, use `BREAKOUT` only for
upside structure and keep direction explicit in provenance.

## 8. Downside Breakdown Semantics

Downside OR breakdown is equally real as a measurement, but it must not become
Portfolio `EXIT`, `AT_RISK`, `DOWNTREND`, or a sell instruction.

Replay:

- OR15 downside only or with other states: 9,216 observations.
- OR30 downside only or with other states: 6,142 observations.
- OR15 and OR30 both downside: 5,854 observations.
- OR15 downside but OR30 upside: 236 observations.

Recommendation: if exposed, use a separate `BREAKDOWN` semantic. If the owner
wants Setup to mean positive long-side opportunity only, downside breakdown
should remain context/provenance and render null.

## 9. Returned-Inside-Range Semantics

The engine records whether price returned inside the relevant range after the
first breakout/breakdown event. Replay found 9,639 observations (27.36%) with
returned-inside behavior in at least one window; among observations with any OR
event, 9,639 / 15,342 had returned inside.

Recommendation: raw event alone is insufficient for production. A future
methodology must choose one deterministic behavior:

- keep the historical event label with `returned_inside=true` provenance;
- render null after return-inside;
- define invalidated/failed separately in a later milestone.

Do not introduce `FAILED_BREAKOUT` in PS-P9B.

## 10. OR15/OR30 Precedence Analysis

No approved precedence exists. Replay shows precedence matters:

- OR15 downside / OR30 no event: 1,189 observations.
- OR15 upside / OR30 no event: 1,076 observations.
- OR15 upside / OR30 downside: 288 observations.
- OR15 downside / OR30 upside: 236 observations.
- OR15/OR30 event mismatch overall: 14,147 observations.

Recommendation: `METHODOLOGY_REQUIRED`. Do not implement until the owner
chooses either OR30-precedence, agreement-required, OR15-early/OR30-final, or
null-on-conflict semantics.

## 11. Structural vs Actionable Setup Decision

Recommended semantic: structural first.

Opening Range should describe the pattern present. EntryQualification, Status,
Next Action, and Key Trigger should continue to own actionability. Coupling
Setup to EntryQualification would duplicate readiness logic and make downside
semantics asymmetric because current EQ v0 is positive long-side readiness.

## 12. EntryQualification Role

EQ should remain context/confirmation only. Replay over this dataset had sparse
EQ coverage because persisted EQ starts later than the full OR sample:

- `NO_EQ`: 32,278 (91.62%).
- `NOT_YET`: 2,033 (5.77%).
- `QUALIFIED`: 532 (1.51%).
- `UNKNOWN`: 389 (1.10%).

Among any OR event observations, only 163 were `QUALIFIED`. This is insufficient
to freeze EQ-confirmed Setup from this replay. Also, no symmetrical bearish EQ
exists for downside confirmation.

## 13. VWAP Role

VWAP remains context only. Existing VWAP semantics are categorical relation to
VWAP with no approved distance threshold. Do not classify `price > VWAP` as
`BREAKOUT`; OR event remains the structural source.

## 14. Intraday Trend Role

Intraday trend remains context only unless the owner later freezes it as a
confirmation requirement. Do not map `BULLISH` to `BREAKOUT` or `BEARISH` to
`BREAKDOWN` without OR evidence.

## 15. RS Role

Relative Strength is contextual participation evidence only. It may be shown in
the human review pack, but Portfolio Setup must not invent RS thresholds or
weights.

## 16. RVOL Role

Relative Volume is contextual participation evidence only. Existing semantics
have categorical relation to same-time baseline, not a surge/spike label.

## 17. D1 Trend Independence

OR events occur under every D1 Trend state:

- Any OR event with D1 `UPTREND`: 6,832.
- Any OR event with D1 `DOWNTREND`: 6,132.
- Any OR event with D1 `MIXED`: 2,378.

Recommendation: D1 Trend remains context, never a Setup gate.

## 18. Decision Independence

OR events also occur across Decision types:

- Any OR event with `WATCH`: 7,476.
- Any OR event with `TRADE`: 3,936.
- Any OR event with `NO_TRADE`: 3,930.

Recommendation: do not require `DecisionType=TRADE` for structural Setup.

## 19. Conviction Independence

Conviction remains independent. PS-P9B found no approved basis to require HIGH
Conviction for a Setup label.

## 20. Key Trigger Independence

Key Trigger remains the exact TradePlan price condition to watch. Setup should
answer what pattern is present. Do not consume or duplicate Key Trigger in OR
Setup.

## 21. Session/Freshness Contract

Future Setup must be keyed by:

- instrument id;
- market session date;
- OR window (`OR15` or `OR30`);
- evidence `as_of`;
- latest completed canonical M5 slot through `as_of`;
- no future M5 slots;
- compatible Decision/EQ session if contextual evidence participates.

Missing, stale, or incoherent OR evidence should render null with provenance.

## 22. Market-Hours Lifecycle

Recommended lifecycle:

- pre-open: null;
- OR formation: null;
- after OR completion before event: null / `NO_CURRENT_SETUP` provenance;
- event observed: candidate structural event;
- later same session: unresolved until owner chooses persistence vs current
  relation behavior;
- returned inside range: unresolved; do not silently keep or erase the label;
- post-close: final session description may be displayable only if the owner
  accepts "latest completed session structure," not "still actionable now."

## 23. Post-Close/Weekend Semantics

Recommendation: if Setup is implemented later, post-close/weekend display must
say it describes the most recent completed trading session. If that owner
meaning is not acceptable, render null outside market hours.

## 24. Candidate Methodologies

Candidate A - raw OR structure:

- Pros: deterministic and threshold-free.
- Cons: too many returned-inside and conflict cases; not safe yet.

Candidate B - OR plus approved confirmation context:

- Pros: may reduce noise.
- Cons: EQ coverage is sparse in this replay; positive EQ is asymmetric and not
  suitable for downside; still risks duplicating actionability.

Candidate C - no production Setup:

- Pros: preserves semantics and avoids unstable labels.
- Cons: owner-facing Setup remains blank.

Recommendation: Candidate C for production now.

## 25. Replay Dataset

Read-only replay used `db/athena.db`, SQLite URI `mode=ro`, and the real
`OpeningRangeEngine` over persisted M5 candles.

Dataset:

- sessions: 2026-08-14 through 2026-09-04 where Decisions existed;
- checkpoints: 09:30, 09:45, 10:00, 11:00, 13:00, 14:30 IST;
- latest per-instrument Decision at each checkpoint, including `NO_TRADE`,
  `WATCH`, and `TRADE`;
- 35,232 instrument-checkpoint observations;
- 398 distinct instruments;
- 6,065 instrument-session groups.

This is a settled market-time replay over the data representation held now, not
a bitemporal knowledge-time reconstruction.

## 26. Replay Results

Overall Decision mix:

- `WATCH`: 17,328 (49.18%).
- `NO_TRADE`: 10,770 (30.57%).
- `TRADE`: 7,134 (20.25%).

D1 Trend mix:

- `UPTREND`: 15,157 (43.02%).
- `DOWNTREND`: 14,726 (41.80%).
- `MIXED`: 5,349 (15.18%).

Any OR event was observed in 15,342 observations. Returned-inside behavior was
common enough to block raw production labeling.

## 27. Event/Transition Distributions

Top event pairs:

- OR15 no event / OR30 not observed: 8,200.
- OR15 not observed / OR30 not observed: 7,288.
- OR15 downside / OR30 downside: 5,854.
- OR15 no event / OR30 no event: 4,402.
- OR15 upside / OR30 upside: 3,541.
- OR15 upside / OR30 downside: 288.
- OR15 downside / OR30 upside: 236.

Same-session groups with both upside and downside observed at some point:
222 / 6,063 replayed multi-checkpoint groups.

## 28. Conflict/Ambiguous Cases

Representative cases:

- `NSE:AEGISLOG`, 2026-08-14 10:00: OR15 upside, OR30 no event.
- `NSE:ADANIENT`, 2026-08-14 10:00: OR15 and OR30 upside, but returned inside.
- `NSE:AARTIIND`, 2026-08-14 10:00: OR15 and OR30 downside.
- `NSE:NSLNISP`, 2026-08-14 11:00: OR15 upside then OR30 downside.
- `NSE:IIFL`, 2026-08-14 11:00: OR15 downside then OR30 upside.
- `NSE:ADANIPORTS`, 2026-08-14 09:45: OR15 upside with returned-inside true.

These cases prove the production method needs explicit conflict and lifecycle
rules.

## 29. Future-Leakage Validation

Research replay reran every observation by supplying later same-day candles
while keeping the original `as_of`. The real `OpeningRangeEngine` produced the
same OR15/OR30 evidence in all cases.

Future-leakage defects: 0.

## 30. Human Review Pack

Suggested review pack fields:

- symbol;
- session;
- analysis `as_of`;
- D1 Trend;
- Decision type;
- EntryQualification state when available;
- OR15 status/relation/event/first event timestamp/returned-inside/current
  extension;
- OR30 status/relation/event/first event timestamp/returned-inside/current
  extension;
- candidate Setup;
- reason/null reason.

The examples in section 28 should be included because they are methodology
stress cases.

## 31. Reason-Code Proposal

Do not freeze names yet. Proposed conceptual reasons:

- `SETUP_BREAKOUT_FROM_OPENING_RANGE`
- `SETUP_BREAKDOWN_FROM_OPENING_RANGE`
- `SETUP_NOT_PRESENT`
- `SETUP_EVIDENCE_UNAVAILABLE`
- `SETUP_EVIDENCE_STALE`
- `SETUP_EVIDENCE_INCOHERENT`
- `SETUP_OR_WINDOWS_CONFLICT`
- `SETUP_RETURNED_INSIDE_RANGE`
- `SETUP_METHODOLOGY_NOT_SUPPORTED`

## 32. Null Semantics

Owner-facing null should distinguish provenance:

- no current setup;
- evidence unavailable;
- evidence stale;
- evidence incoherent;
- OR windows conflict;
- returned-inside invalidates label if owner chooses that rule;
- methodology not supported.

Do not expose `UNKNOWN` unless separately approved.

## 33. Interpretation-Version Recommendation

Production remains `portfolio-interpretation-v2` during PS-P9B.

If a future milestone populates Setup, use `portfolio-interpretation-v3`.

## 34. Explicit Owner Decisions

Recommendations:

| Decision | Recommendation |
|---|---|
| Structural or actionable? | Structural first. |
| Is upside OR breakout sufficient? | Not yet; lifecycle/precedence unresolved. |
| Should downside OR breakdown be owner-facing? | Only if owner accepts `BREAKDOWN` as structural context, not EXIT. |
| If yes, label? | `BREAKDOWN`, not generic `BREAKOUT`. |
| Is generic BREAKOUT ambiguous? | Yes for all OR events; acceptable only for upside. |
| OR15 vs OR30 precedence? | Methodology required. |
| OR15-only valid? | Not frozen; replay shows many cases. |
| OR30-only valid? | Not observed as OR15 no-event/OR30-up in this sample; still not frozen. |
| OR15/OR30 conflict? | Null or explicit conflict provenance until owner decides. |
| Returned-inside behavior? | Must be explicit; recommend no production label until decided. |
| Persist entire session? | Not frozen. |
| Persist after close? | Only as latest-session structure, not current actionability. |
| Weekend/holiday display? | Null unless latest-session semantics are accepted. |
| EQ confirms Setup? | Keep context only for now. |
| VWAP participates? | Context only. |
| Intraday trend participates? | Context only. |
| RS/RVOL participate? | Context only. |
| DecisionType independent? | Yes. |
| D1 Trend independent? | Yes. |
| Missing/stale/incoherent -> null? | Yes, with provenance. |
| Distinguish no-setup vs unavailable? | Yes in provenance. |
| Replay acceptable? | Acceptable for finding risk; not enough to approve production Setup. |
| Future implementation version? | `portfolio-interpretation-v3`. |
| Smallest PS-P9C? | Owner decision/freeze on directionality, OR15/OR30 precedence, and lifecycle only. |
| If not approved? | Keep Setup deferred. |

## 35. Recommended PS-P9C or Deferral

Recommended immediate outcome: defer production Setup.

If the owner wants to continue, PS-P9C should be another methodology freeze,
not production implementation. Scope it to three owner decisions only:

- directionality: positive-only `BREAKOUT` vs directional `BREAKOUT` /
  `BREAKDOWN`;
- OR15/OR30 precedence or null-on-conflict;
- returned-inside and post-close lifecycle.

Only after those are approved should implementation be considered.

## 36. Files Changed

Created:

- `docs/research/PS-P9B-PORTFOLIO-OPENING-RANGE-SETUP-METHODOLOGY-REPLAY.md`

Modified:

- `docs/research/PS-P9A-PORTFOLIO-SETUP-METHODOLOGY-DISCOVERY.md`
- `docs/MILESTONES.md`
- `IMPLEMENTATION_SUMMARY.md`
- `ATHENA_BRIEFING.md`

No production source files changed for PS-P9B.

## 37. Validation

Documentation/research validation:

- `git diff --check`: clean.
- `uv.lock` status check: untouched.
- schema/API/dashboard status check: no PS-P9B changes.
- Portfolio interpretation status check: production remains
  `portfolio-interpretation-v2`; Setup remains deferred with
  `SETUP_METHODOLOGY_DEFERRED`.

## 38. Suggested Commit Message

```text
docs(portfolio): replay Opening Range Setup methodology

- Mark PS-P9A owner-approved and frozen with Setup still deferred.
- Add PS-P9B replay showing raw OR events need direction and lifecycle rules.
- Recommend keeping production Setup null until OR precedence and conflicts are frozen.
```
