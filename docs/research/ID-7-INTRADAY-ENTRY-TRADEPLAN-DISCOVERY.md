# ID-7 — Intraday Entry / TradePlan Discovery & Architecture Contract

**Status:** ID-7 DISCOVERY COMPLETE — implementation NOT started, NOT
authorized by this document. Owner/Chief Architect authorized discovery-only
on 2026-09-03, following ID-0 through ID-6 all owner-approved/closed (ID-6
final classification `REPLAY_AND_SHADOW_BEHAVIORALLY_SOUND`).

Everything below is source-grounded (file:line citations throughout) —
produced by direct repository inspection, not from memory of prior
conversation summaries. Where evidence was genuinely unavailable, this
document says so explicitly rather than guessing.

---

## 1. Executive summary

ATHENA's current `TradePlan` is a **daily-only, ATR-multiple construct**
(`entry = last_close`, `stop = last_close ± 1.5×ATR(D1)`, `target =
last_close ± 3.0×ATR(D1)`, R:R always exactly 2.0) computed once, at Decision
time, from D1 indicators alone. **Zero intraday evidence — no M5/M15
candles, VWAP, ORB, RelativeStrength, RelativeVolume, GapContext,
SessionContext, or EntryQualification — feeds it today**, and it structurally
cannot be retrofitted to consume `EntryQualification`, because
`EntryQualification` is evaluated *after* the Decision (and its `TradePlan`)
already exist, and only WATCH/TRADE Decisions get one — TradePlan is
TRADE-only by a hard domain invariant.

Meanwhile, `EntryQualification` (ID-6) evaluates WATCH-heavy production
traffic (6,640/6,640 rows in the ID-6E final audit were WATCH) using real
intraday M5 evidence, correctly tagged `LIVE_M5_PROVISIONAL`, bound tightly
to a specific `decision_id` via FK. It answers *whether* a candidate is
intraday-ready — never *where* to enter, *where* to stop, or *whether* there
is reward headroom.

A newly-discovered, load-bearing fact: production `entry_qualification`
writes for a REFRESH cycle cluster in the **final ~5-7 seconds** of a
~550-560 second cycle. This means the entire 11-stage, 528-instrument
analytical scan completes very fast — the ~9-10 minute latency is spent
almost entirely **before** the scan loop, most plausibly in the sequential,
per-instrument, non-batched **ingestion** phase (candle/quote fetch), not in
indicator/scoring/decision computation. This is circumstantial (no
stage-level instrumentation exists to prove it directly) but it is the
single most important finding for ID-7's temporal-actionability problem.

The evidence strongly favors **Option B** in §32/§33 below: a **new,
separate intraday actionability artifact**, bound to `(decision_id,
entry_qualification identity)`, left entirely orthogonal to the existing
`TradePlan` — not a retrofit. This mirrors the exact architectural move
ADR-013 already made for `EntryQualification` itself relative to `Decision`.

## 2. Scope / non-scope

**In scope for this document:** architecture discovery, evidence inventory,
options analysis, a recommended architecture, a recommended sub-milestone
sequence, and a small set of owner policy questions.

**Explicitly out of scope (per owner instruction) and not done here:**
freezing numeric entry/stop/target thresholds; tuning `EntryQualification`;
profitability fitting/backtesting; position sizing; live-plan supervision;
any production source change beyond this document and status-line updates
in the four named tracking docs; drafting an ADR (only a recommendation that
one is needed); starting ID-7A/ID-7A0; touching `DecisionEngine`,
`TradePlan`, EMR, or DarvaX.

## 3. Frozen ID-6 upstream contract

Treated as an immutable upstream boundary throughout this discovery, per
owner instruction — none of the following was modified or reinterpreted:

- **v0 readiness formula:** `VWAP positive AND aggregate intraday trend ==
  BULLISH AND (RS support OR RVOL support)` — confirmed literally at
  `src/athena/intraday/entry_qualification_engine.py:2-16,304-330`.
- **State enum:** `QUALIFIED, NOT_YET, UNKNOWN, DISQUALIFIED_FOR_SESSION,
  EXPIRED, OUT_OF_SCOPE` (`entry_qualification_models.py:22-37`); the engine
  never emits `DISQUALIFIED_FOR_SESSION` in v0.
- **Evidence finality enum:** `LIVE_M5_PROVISIONAL, UNKNOWN_PROVENANCE,
  NO_DECISIVE_PROVISIONAL_M5_DEPENDENCY` (`:40-52`) — caller-supplied, never
  inferred by the engine.
- **Confirmation enum:** `NOT_EVALUATED, CONFIRMED_BY_POLICY, NOT_CONFIRMED,
  UNKNOWN` (`:55-61`) — v0 always emits `NOT_EVALUATED`.
- **Persistence:** `entry_qualifications` table (`data/store/schema.py:461-
  479`), append-only, PK `(instrument_id, session_date, as_of, decision_id,
  methodology_version)`, FK `decision_id REFERENCES decisions(decision_id)`.
- **ADR-013's orthogonality lesson:** Qualification State, Evidence
  Finality, and Qualification Confirmation are independent dimensions,
  never collapsed into one enum (`docs/adr/ADR-013-...md:59-98`).

ID-7 may **consume** these artifacts freely. Nothing in this discovery
proposes changing their meaning, adding hysteresis/debounce/cooldown/
stickiness, new thresholds, a weighted score, or new confirmation semantics
to `EntryQualification`.

## 4. Current TradePlan architecture

`TradePlan` (`src/athena/domain/decision.py:14-36`), an immutable, frozen,
slotted dataclass nested **inside** `Decision.trade_plan`
(`decision.py:131`) — it has **no independent identity, no primary key of
its own, and no dedicated table**:

```python
@dataclass(frozen=True, slots=True)
class TradePlan:
    """Actionable plan attached to a TRADE decision. ATHENA never executes it."""
    entry_low: Decimal
    entry_high: Decimal
    stop_loss: Decimal
    targets: tuple[Decimal, ...]
    position_size: int
    risk_amount: Decimal
    risk_reward: Decimal
    valid_from: datetime
    valid_until: datetime
```

`Decision.__post_init__` (`domain/decision.py:138-140`) **requires**
`trade_plan is not None` when `decision_type is TRADE`, and TradePlan is
**never** attached to WATCH/NO_TRADE/other Decision types
(`decision/engine.py:141-158`) — a hard structural invariant, not a
convention.

Schema (`data/store/schema.py:214-229`): `trade_plan_json` is a nullable
`TEXT` column embedded directly in the `decisions` table — no FK, no
separate PK, no index, unlike `entry_qualifications`'s real, independently
identifiable rows.

## 5. Current TradePlan formulas

`DecisionEngine._build_plan` (`decision/engine.py:232-266`):

```python
last_close_raw = sma.evidence.inputs.get("last_close")
atr_val = atr.values["value"]
if atr_val <= _ZERO:
    return None
stop_dist = atr_val * Decimal(str(cfg.atr_stop_multiple))
target_dist = atr_val * Decimal(str(cfg.atr_target_multiple))
if direction is Direction.LONG:
    stop = last_close - stop_dist
    target = last_close + target_dist
else:
    stop = last_close + stop_dist
    target = last_close - target_dist
risk_reward = target_dist / stop_dist
```

Config (`config/decision.json`, `DecisionPlanCfg` in
`src/athena/config/models.py:1020-1024`):

```json
"plan": {
  "atr_stop_multiple": 1.5,
  "atr_target_multiple": 3.0,
  "default_units": 1,
  "validity_hours": 6
}
```

- **Entry**: a single point (`entry_low == entry_high == last_close`), not
  a range — sourced from the daily SMA indicator's own `last_close` input,
  itself built from D1 candles only.
- **Stop**: `last_close ± 1.5 × ATR(D1)`.
- **Target**: a single target at `last_close ± 3.0 × ATR(D1)` — **not**
  literally +1%/+1.5%, and not configured as a percentage anywhere.
- **R:R**: always exactly `3.0/1.5 = 2.0` — a constant ratio of two ATR
  multiples, never a computed reward relative to a real fill or a resistance
  level.
- **Position size**: hardcoded `default_units=1`, explicitly documented as
  "a provisional unit, NOT a capital-based size" (`engine.py:10-11`).
- **Validity**: `[as_of, as_of + 6 hours)`.

If ATR or SMA is missing/not `OK`, or `direction is Direction.NONE`
(e.g. SIDEWAYS regime — see the earlier in-chat explanation this same
session), `_build_plan` returns `None` and no TradePlan is attached even to
an otherwise TRADE-eligible Decision.

## 6. Current persistence/API/UI flow

1. Ingestion → `candles` table (`schema.py:107-119`).
2. `OwnerValidationPipeline._scan_eligible` (`ops/owner_validation.py:782`)
   builds one 11-stage `WorkflowDefinition` per instrument.
3. Indicators (D1 only) → `ind_stage` (`owner_validation.py:938-950`) →
   `IndicatorEngine.compute_all` (`indicators/engine.py:62`).
4. Scoring/Confidence/Risk → `sco_stage`/`conf_stage`/`risk_stage`
   (`:1080-1129`).
5. Decision + TradePlan → `dec_stage` (`:1131-1157`) →
   `DecisionEngine.decide` (`decision/engine.py:66`) → `_build_plan`
   (`:232`).
6. Persistence → `repo.save_decision(...)` (`owner_validation.py:1146`) →
   `SqliteRepository.save_decision` (`data/store/repository.py:903-926`),
   an `INSERT ... ON CONFLICT(decision_id) DO UPDATE` upsert, in practice
   append-only since `decision_id` embeds the cycle timestamp.
7. API → `GET /v1/decisions/{decision_id}` (`api/v1/routers/decisions.py:171`)
   → `TradePlanDTO` composed in
   `api/v1/services/decisions_service.py:262-280`; also
   `GET /v1/decisions/{decision_id}/plan-freshness` (`decisions.py:254`).
8. Dashboard → `api/static/js/13-decision-brief-core.js`, `renderTradePlan`
   (line 1003), entry/stop/target reads (lines 71-128, 591-654, 789-933),
   chart overlay (line 1193).

**Decision/TradePlan lifecycle**: no explicit "superseded" column or flag
anywhere in `decisions` schema. "Latest" is a pure query pattern
(`list_latest_decisions_by_instrument`, `repository.py:1024-1047`, a
`ROW_NUMBER() OVER (PARTITION BY instrument_id ORDER BY ts DESC, decision_id
DESC)` window). Any historical `decision_id` — including from a superseded
cycle — remains fully queryable by direct ID lookup with no "is this still
current" filter. Confirmed advisory-only: no order-placement code anywhere
in `src/athena/` (repo-wide grep returns zero hits); `TradePlan`'s own
docstring: *"ATHENA never executes it."*

## 7. Existing intraday evidence inventory

| Artifact | Module | Timeframe | Persisted? | Point-in-time character |
|---|---|---|---|---|
| `SessionContext` | `session/` | D1 calendar + M5/M15 quality | **No** — recomputed every cycle, no table, `data_quality` confirmed absent from every schema | Live-derived |
| `GapContext` (ID-5C) | `intraday/gap_models.py` | D1-only | No | Settled D1, replay-safe |
| `OpeningRangeEvidence`/OR15/OR30 (ID-3) | `intraday/opening_range_models.py` | Completed M5 | No | `LIVE_M5_PROVISIONAL`-eligible; real price levels (`high`/`low`), explicitly "measurements only — no trade meaning" |
| VWAP | `indicators/calculations.py:196-225` | Completed M5, session-cumulative | No (computed fresh) | `LIVE_M5_PROVISIONAL`-eligible |
| `RelativeStrengthContext` (ID-4) | `intraday/relative_strength_models.py` | Completed M5 | No | `LIVE_M5_PROVISIONAL`-eligible |
| `RelativeVolumeContext` (ID-5D) | `intraday/relative_volume_models.py` | Completed M5, cumulative same-time-of-day | No | `LIVE_M5_PROVISIONAL`-eligible |
| `EntryQualification` (ID-6) | `intraday/entry_qualification_*` | Derived from the above | **Yes** — `entry_qualifications` table | Explicit `LIVE_M5_PROVISIONAL` field |
| `RegimeEngine` (market trend) | `regime/` | D1 | Implicitly via Decision | Settled D1 |
| `SectorHealthEngine` | `sector_health/` | D1 | Implicitly via Decision | Settled D1 |

**No canonical support/resistance computation exists anywhere** (no pivot
point, no prior-day high/low helper, no swing-high/low detector) in
`indicators/`, `risk/`, or `scoring/`. The only real price-level artifacts
in the whole repository are `OpeningRangeFormation.high/low` (unused for
stop/target today) and DarvaX's isolated `fibonacci_levels()`
(`darvax/primitives/levels.py:60-111`, caller-supplied swing points — no
in-repo swing detector feeds it, and DarvaX is architecturally isolated
from canonical Decision/TradePlan per ADR-010).

**No "alignment score"** fuses market/sector/stock trend into one number —
`RegimeEngine`, `SectorHealthEngine`, and `RelativeStrengthContext` remain
three separate, differently-scoped classifiers today (confirmed: repo-wide
grep for "alignment" returns nothing relevant).

**Quote freshness vs. candle completeness are genuinely distinct concepts**
in the code (`session/engine.py:36-69` for completeness;
`SessionContext.latest_quote_ts` for freshness), but **no staleness/age
threshold exists on the quote timestamp anywhere** — it is only checked for
presence (`QUOTE_UNAVAILABLE` fires solely when `latest_quote_ts is None`,
`session/engine.py:374-375`).

## 8. EntryQualification integration point

`entry_qualification_stage` (`owner_validation.py:1394-1414`) depends on
`("decision", "intraday_analytics")` and reads `box["cap"].outcome.decision`
— the **already-finalized, already-persisted** Decision. It is strictly
**downstream/consumer**, never an input to Decision or TradePlan, and
structurally cannot be, since `DecisionEngine.decide()`'s signature
(`engine.py:66-81`) has no `entry_qualification` parameter at all. Any
future coupling in the other direction (EntryQualification influencing
Decision/TradePlan) would require modifying `DecisionEngine` — explicitly
out of scope for this discovery and, per owner instruction, not to be
designed here.

## 9. Temporal-actionability problem

Production evidence (ID-6E final audit, full 2026-09-03 session, 6,640
rows): `persisted_at - as_of` median 562.97s (≈9.38 min), p90 588.42s, p95
592.52s, max 622.71s, 0 negative. Per-checkpoint medians stayed in a narrow
543.9-619.3s band across all 26 normal cycles — stable all session, not an
opening-cycle artifact.

**QUALIFIED at market state `T` does not imply actionable at wall-clock `T +
~9-10 min`.** This is the central problem ID-7 exists to solve
architecturally (not numerically, not in this document).

## 10. Stage-level latency audit

No existing instrumentation can directly attribute the ~9-10 minutes to a
specific pipeline stage — `src/athena/observability/` is a documented but
**unused skeleton** (zero call sites in `owner_validation.py`,
`scanner.py`, `dry_run.py` — confirmed by grep); `WorkflowEngine`'s own
per-stage timing (`runtime/workflow.py:146-181`) is driven by a fake
`_MonoClock` (`owner_validation.py:50-56`, +1.0/call, built for
deterministic tests) — not wall time — and is never read by the caller
besides.

The **one real wall-clock number persisted anywhere** is a single
whole-cycle `duration_seconds` in `runs.detail_json`
(`scheduling/dry_run.py:111,155`) — ingestion + full scan combined, not
split.

**New evidence, derived directly from `db/athena.db` for this discovery**
(read-only query, not new instrumentation): within a single REFRESH cycle,
all `entry_qualifications` writes for that cycle cluster in a **~5-7 second
window at the very end** of the cycle — e.g. `as_of=09:15:16`,
`persisted_at` offsets range only 553.3s-558.1s across all 255 rows, out of
a 556.9977s total cycle duration; the same pattern holds for every other
2026-09-03 REFRESH cycle checked. **This means the full 11-stage,
528-instrument analytical scan (indicators → scoring → decision →
entry-qualification) completes in roughly the last few seconds of the
cycle** — the preceding ~550 seconds happen before the scan loop
meaningfully progresses.

`LiveIngestionEngine.run_cycle` (`data/ingestion/engine.py:69`) fetches
daily candles and intraday candles in **two separate sequential
per-instrument loops** (`for iid in ids: ... daily_candles(...)`, then
`for iid in ids: ... intraday_candles(...)`) — only `quotes(ids)` is a
single batch call. Universe size confirmed 528
(`SELECT count(*) FROM owner_candidates WHERE active=1`).

**Conclusion (circumstantial, not proven by direct instrumentation): the
dominant latency source is most plausibly sequential, per-instrument,
non-batched ingestion (candle fetch), not indicator/scoring/decision
computation.** This should not be treated as definitively proven — see
§38 Owner Question 5 for how to close this evidentiary gap before
committing to an architectural response.

## 11. Cadence-vs-processing-vs-evidence-age distinction

Three structurally distinct numbers, confirmed separately in code and data:

- **Cadence** (how often a new cycle *starts*): `config/base.json:15`,
  `"refresh_interval_minutes": 15`, gated by `is_refresh_due()`
  (`scheduling/cadence.py:45-69`). Confirmed via DB: REFRESH `started_ts`
  values on 2026-09-03 are ~13-15 minutes apart.
- **Processing duration** (how long one cycle *takes*): `duration_seconds`
  in `runs.detail_json`, ~550-565s (~9.2-9.4 min) per cycle — a
  ~96% duty cycle relative to the 15-minute cadence.
- **Evidence age at consumption time** (§9): a downstream consumer of
  `EntryQualification` at wall-clock time `T` is reading evidence computed
  at `as_of ≈ T - 9 to 10 min` — a distinct, consumer-side concept that
  neither cadence nor processing-duration alone captures, and that will
  compound further if a future actionability check is itself computed some
  time after `persisted_at`.

## 12. Candidate entry price sources

| Source | Semantic meaning | Timeframe/timestamp | Provisionality | Persisted? | Replay-safe? | Suitability |
|---|---|---|---|---|---|---|
| `TradePlan.entry_low/high` | Daily last close | D1, settled | Settled | Yes (embedded JSON) | Yes | Analytical reference only — 9-10 min stale by the time it's consumable intraday |
| Daily `last_close` | Same as above | D1 | Settled | Via TradePlan | Yes | Same |
| Latest quote | Live tick price | Live, timestamp-checked-for-presence-only | Live/provisional | No — not modeled as a domain field anywhere audited | No | **Not currently a well-defined domain object** — would need a new field if used as trigger price |
| Latest completed M5 close | Most recent settled 5-min bar | M5, completed-gated | `LIVE_M5_PROVISIONAL` | No (derivable from `candles`) | Partially — live-provisional vs. later-settled M5 can differ (ID-5B finding) | Reasonable trigger reference if finality is explicitly tagged |
| Forming/current M5 | Incomplete bar | M5, not yet closed | Live, not yet even provisional-settled | No | No | **Should not be used** — violates the `completed_candles` gate pattern used everywhere else in the codebase |
| VWAP | Session-cumulative volume-weighted price | M5-derived | `LIVE_M5_PROVISIONAL` | No | Partially | Candidate trigger/context reference, not itself a fill price |
| OR high/low | Opening-range bounds | M5, completed | `LIVE_M5_PROVISIONAL` | No | Partially | Candidate breakout trigger reference, not a fill price |
| Breakout/reclaim levels | — | — | — | Not computed anywhere today | — | Would need new methodology |
| Support/resistance levels | — | — | — | **Do not exist in the codebase** | — | Would need new methodology |
| Persisted trigger price | — | — | — | Does not exist | — | Would need new field |

No price source should be chosen merely because it is freshest — per
instruction, this table is inventory only, not a selection.

## 13. Candidate entry-trigger methodologies

Discovery-only inventory, none adopted, none implemented, no percentages or
weighted scores invented:

- **Immediate market-reference entry** — technically available today
  (latest quote or latest completed M5 close), but the "trigger" concept
  itself (a rule that fires an entry) does not exist anywhere in the
  codebase currently.
- **Breakout trigger** — `OpeningRangeEvidence.breakout_event`
  (`UPSIDE_BREAKOUT_EVENT`/`DOWNSIDE_BREAKDOWN_EVENT`) already exists as a
  measurement, unused for triggering; would need a decision rule layered on
  top.
- **VWAP reclaim/hold** — `VwapEvidence.relation` exists
  (`ABOVE_VWAP`/`BELOW_VWAP`/`AT_VWAP`); a "reclaim" (cross event over
  time) is not currently modeled — only a point-in-time relation.
- **Pullback/retest, ORB breakout/retest, structure breakout, continuation
  after consolidation** — none currently represented by any persisted or
  computed artifact; all would require new signal methodology built from
  scratch (a §31 methodology item, not architecture).

## 14. Candidate stop/invalidation sources

| Source | Availability | Timeframe | Point-in-time safe? | Persisted? | Provisional? |
|---|---|---|---|---|---|
| Intraday swing low | Not computed anywhere | — | — | No | — |
| VWAP | Available (indicator) | M5 | Partially | No | `LIVE_M5_PROVISIONAL` |
| OR low | Available (`OpeningRangeFormation.low`) | M5 | Partially | No | `LIVE_M5_PROVISIONAL` |
| Breakout/retest level | Not computed | — | — | No | — |
| Daily support | Does not exist | — | — | No | — |
| Intraday support | Does not exist | — | — | No | — |
| Previous candle structure | Raw candles exist; no derived "structure" | M5/D1 | Yes (D1) / partial (M5) | Candles yes, derived structure no | Depends |
| ATR | Available (D1 only today) | D1 | Yes | Via TradePlan | Settled |
| Gap reference | Available (`GapContext`) | D1 | Yes | No | Settled |

No stop-selection precedence is frozen here — this is inventory only, per
instruction.

## 15. Candidate target/resistance sources

| Source | Availability |
|---|---|
| Resistance levels (generic) | Does not exist anywhere in the codebase |
| Previous-day high | Derivable from D1 candles, not currently exposed as a named field |
| OR high | Available (`OpeningRangeFormation.high`) |
| Intraday swing highs | Not computed |
| Daily resistance | Does not exist |
| ATR-derived ranges | Available (today's `TradePlan.targets` mechanism) |
| Gap levels | Available via `GapContext` (D1 only) |

**Owner's stated concern is validated by evidence**: nothing in the current
codebase checks structural headroom before proposing a target — the
existing `TradePlan` target is a pure ATR multiple that can pass through a
real resistance level with no awareness that it did so, because no
resistance concept exists to check against. This is a genuine
methodology-research gap, not solvable by architecture alone (§31).

## 16. Current risk/reward behavior

R:R is computed in `_build_plan` (`decision/engine.py:265`) as
`target_dist / stop_dist`, which reduces to a **constant**
(`atr_target_multiple / atr_stop_multiple = 2.0`) regardless of instrument,
regardless of any real resistance/reward feasibility. It is persisted
(inside `trade_plan_json`) and does not influence `DecisionEngine`'s own
TRADE/WATCH/NO_TRADE branching (that gate is `composite >= threshold` plus
`direction is not NONE` plus `plan is not None` — R:R itself is not a gate
condition). No minimum-R:R policy exists anywhere. No reward-truncation-by-
resistance exists (§15). No stop-distance min/max policy exists.

## 17. Session/expiry semantics

`TradePlan.valid_from/valid_until` (`decision.py:22-23`) gives a flat
6-hour validity window from `as_of` — it does not consult `SessionContext`
phase at all (no `PRE_OPEN`/`REGULAR`/`CLOSED`-aware logic found in
`_build_plan`). There is no early/mid/late-session distinction anywhere in
current TradePlan logic.

`EntryQualification`, by contrast, is inherently point-in-time and
non-sticky — evaluated fresh every cycle with no persisted expiry field of
its own (its own "freshness" is entirely a function of how recently
`persisted_at` occurred relative to the consumer's wall-clock time).

Candidate invalidation events for a **future** entry-actionability artifact
(inventory only, none selected, no durations invented): a newer canonical
Decision superseding the one this artifact is bound to; a newer
`EntryQualification` observation no longer `QUALIFIED`; a session-phase
transition (e.g. REGULAR→CLOSED); meaningful price displacement from the
qualification-time price; a structure break; a freshness/age breach beyond
some threshold (not proposed here).

## 18. Decision churn/supersession implications

Confirmed by the ID-6E final audit: 295/301 (98.01%) REGULAR
instrument/session groups showed more than one distinct `decision_id`
across a single session — production issues a fresh canonical Decision per
instrument, per cycle, unconditionally. No "superseded" flag exists on
`decisions` (§6). Any historical `decision_id` remains fully queryable via
direct API lookup with no "is current" filter.

**Implication for ID-7**: any future entry-actionability artifact **must**
bind to an exact `decision_id` (not "the instrument's current Decision"),
exactly as `EntryQualification` already does — otherwise the API/dashboard
could silently present an actionability verdict computed against a Decision
that has since been superseded by a newer cycle's Decision. This is
identity discipline, not a new invention — it directly reuses ID-6C.1's
already-accepted binding-invariant pattern.

## 19. Proposed identity/provenance contract

Derived from ID-6C's own accepted key pattern
(`(instrument_id, session_date, as_of, decision_id, methodology_version)`,
`docs/design/ID-6C-ENTRY-QUALIFICATION-PERSISTENCE.md` §3), extended for a
future entry-actionability artifact that additionally binds to a specific
`EntryQualification` identity (since EntryQualification is itself keyed by
`(instrument_id, session_date, as_of, decision_id, methodology_version)`,
binding to all of those transitively binds to one EQ observation):

**Architectural (freeze-able now, no fitting required):**
`instrument_id`, `session_date`, `decision_id` (FK to `decisions`),
`entry_qualification_as_of` + `entry_qualification_methodology_version` (FK
composite to `entry_qualifications`), `run_id`, `cycle_id`,
`evaluation_as_of` (the moment this artifact's own logic ran —
architecturally distinct from `entry_qualification_as_of`),
`persisted_at` (via an injectable persistence clock, mirroring ID-6D.1's
separation of evaluation-time from persistence-time), `methodology_version`
(this artifact's own, independent of EntryQualification's), `config_
snapshot_id`, `evidence_refs`.

**Not architectural — requires methodology research (§31):** whether
`market_data_as_of`/`quote_as_of` need to be separate fields (only if a
future revalidation step consumes evidence fresher than the EQ observation
it's bound to — an open design question, not resolved here).

This document explicitly distinguishes **market/evidence time**
(`entry_qualification_as_of`), **evaluation time** (`evaluation_as_of`),
**persistence time** (`persisted_at`), and **wall-clock actionability time**
(the consumer's own "now" at read time — never itself persisted, always
computed at the point of use) — the same four-way distinction ID-6D.1
already established is necessary, generalized to one more layer.

## 20. Point-in-time/replay classification

| Input | Classification |
|---|---|
| D1 candles (ATR, SMA, last_close) | `POINT_IN_TIME_SAFE` — settled, replay-safe |
| Completed M5 candles (VWAP, ORB, RS, RVOL) | `LIVE_PROVISIONAL_ONLY` when read live; a later replay reads the *settled* historical representation, which ID-5B already proved can differ from what was live-provisional at the time — so historical replay of these inputs is **not** a guarantee of reproducing live knowledge-time behavior |
| Latest quote | `LIVE_PROVISIONAL_ONLY`, and largely `NOT_REPLAYABLE_WITH_CURRENT_INFRASTRUCTURE` — no historical quote-tick store was found in this audit |
| `entry_qualifications` (persisted) | `POINT_IN_TIME_SAFE` for what was persisted (immutable observation), but the *evidence it was computed from* remains `LIVE_PROVISIONAL_ONLY` at evaluation time |
| Any future entry-actionability artifact evidence | Inherits `LIVE_PROVISIONAL_ONLY` for any M5-sourced component, `POINT_IN_TIME_SAFE` for any D1-sourced component — must be tagged explicitly per §21, not assumed uniform |

Per instruction: do not claim historical replay reproduces exactly what a
live provider knew at the time — this classification exists precisely
because ID-5B already showed that claim is false for M5 data.

## 21. LIVE_M5 provisionality implications

Any future entry/stop/target input drawn from VWAP, ORB, RS, or RVOL
inherits `LIVE_M5_PROVISIONAL`-type provisionality. **Recommendation:
EntryQualification finality and a future EntryPlan's own evidence finality
should be independent fields**, not reused blindly — because a future
actionability artifact may consume *additional* evidence (e.g. OR
high/low, or a later, fresher M5 read than the one EntryQualification was
computed from) with its own, potentially different, provenance. This
mirrors ADR-013's own reasoning almost exactly and is a direct, low-risk
extension of an already-accepted architectural pattern.

## 22. Quote-vs-candle freshness implications

Confirmed genuinely distinct (§7). A future entry-actionability artifact
that uses a live quote as a trigger/reference price must not assume that
because the latest completed M5 candle is fresh, the quote is also fresh
(or vice versa) — no code today enforces or even checks this jointly. This
is a genuine architectural requirement to state explicitly in any future
ADR/domain model (an "evidence coherence" check analogous to ID-6B.2A's
"input-coherence hardening" for EntryQualification), not something that can
be assumed away.

## 23. Artifact role classification

| Artifact | Qualification input | Entry trigger | Entry revalidation | Stop/invalidation | Target/resistance | Risk/reward context | Explanation only | Not appropriate |
|---|---|---|---|---|---|---|---|---|
| `SessionContext` | ✓ (via EQ) | | ✓ (phase gating) | | | | ✓ | |
| `GapContext` | | | | | possible (D1 gap ref) | | ✓ | |
| `OpeningRangeEvidence` | | possible (breakout) | possible | possible (OR low) | possible (OR high) | | ✓ | |
| VWAP | ✓ (via EQ) | possible (reclaim) | possible | possible | | | ✓ | |
| `RelativeStrengthContext` | ✓ (via EQ, support leg) | | possible | | | | ✓ | not a price-level source |
| `RelativeVolumeContext` | ✓ (via EQ, support leg) | | possible | | | possible (liquidity proxy) | ✓ | not a price-level source |
| `EntryQualification` | — (it *is* the qualification) | | ✓ (its own state is the revalidation signal) | | | | ✓ | should not be re-derived downstream |
| `RegimeEngine`/`SectorHealthEngine` | (indirect, via Decision) | | | | | | ✓ | too coarse (D1) for intraday trigger/stop/target |

"Possible" entries are candidates requiring methodology research (§31), not
adopted roles. No artifact is automatically promoted into the entry formula
— several existing artifacts remain explanation-only.

## 24. Market-sector-stock alignment boundary

No fused alignment score exists today (§7). `RelativeStrengthContext`
already quantifies stock-vs-sector-vs-market comparative performance at the
M5 level, independent of `RegimeEngine`/`SectorHealthEngine`'s own D1
classifications. **Recommendation: alignment consumption, if needed for
ID-7's entry logic, should reuse `RelativeStrengthContext` as-is** (it
already exists and is already consumed by `EntryQualification`'s support
leg) rather than inventing a new fused score — a genuinely later
methodology milestone concern, not something ID-7's architecture needs to
solve now.

## 25. Execution-quality boundary

Per this session's owner authorization, execution quality (turnover,
spread, depth, traded value, RVOL, impact-cost proxy) is associated with a
future **ID-11** — note: this association exists **only** because the
owner's own message in this conversation asserts it; no prior repository
documentation defined ID-8 through ID-11's scope before this session (§30
of the ADR/roadmap research agent's findings: zero mentions found).
Currently-available data: `RelativeVolumeContext` (a liquidity/volume
proxy already exists); no spread/depth/turnover/impact-cost data source was
found anywhere in the codebase. **Recommendation: ID-7 needs, at most, a
narrow interface placeholder** for execution-quality context (e.g. an
optional field on a future entry artifact for "liquidity context") — not
the full ID-11 capability pulled forward.

## 26. Position-sizing boundary

Associated with a future **ID-9** by this session's owner authorization
(same caveat as §25 — not pre-existing repository doctrine).
**Recommendation: ID-7 must expose, not compute, what a future sizing
milestone needs**: entry/reference price, stop/invalidation price, risk
per share (`entry - stop`, direction-aware), target/headroom information,
and full provenance (§19) — no capital/account/risk-budget logic belongs
in ID-7.

## 27. Live-supervision boundary

Associated with a future **ID-10** by this session's owner authorization
(same caveat). **Recommendation: ID-7's future artifact should expose a
state model expressive enough for ID-10 to later determine** still valid /
invalidated / target reached / stop reached / expired / superseded —
without ID-7 itself implementing any of that supervision logic. This maps
directly onto the failure/UNKNOWN semantics discussion in §30 below — the
same state model likely serves both purposes.

## 28. API/UI implications

Current TradePlan reaches the dashboard via `13-decision-brief-core.js`
inside the existing Decision Brief surface, tightly coupled to the daily
swing-TradePlan semantics (§6). A future intraday entry artifact should
**not** be exposed by silently repurposing this same rendering path — doing
so risks presenting a stale, superseded, or expired intraday entry as
though it were the same kind of object as a fresh daily TradePlan. No UI
redesign is proposed here (out of scope), but the contract-level
implication is clear: any future surface must make **evidence time,
finality, and expiry/supersession status visible**, exactly as the
Experimental EMR panel (EM-6B) was required to make its own scan-age
visible rather than hiding it — the same transparency principle applies.

## 29. Persistence recommendation (proposal only — no schema created here)

Following ID-6C's accepted convention almost exactly: **append-only**,
never a mutable "current" row; composite identity key per §19; a repository-
level binding-invariant check analogous to ID-6C.1's (verifying
`decision_type`/`run_id`/`cycle_id`/`instrument_id` agreement with the bound
Decision, and additionally with the bound EntryQualification, before
insert) — never silently downgrading a mismatch to `UNKNOWN`; "latest"
exposed only as a query pattern (by market-time `evaluation_as_of`, not by
write-time), mirroring `list_latest_decisions_by_instrument`'s window-
function approach. No schema is created and no schema version is bumped in
this document, per instruction.

## 30. Failure/UNKNOWN semantics

Following ADR-013's own precedent of treating missing evidence as distinct
from negative evidence, a candidate future state model (**examples only,
not frozen**): `UNKNOWN` (evidence not yet resolvable — analogous to EQ's
own `UNKNOWN`), `NOT_ACTIONABLE_YET` (evidence resolved, conditions not
met — analogous to `NOT_YET`), `ACTIONABLE`, `INVALIDATED` (a structural
condition broke after having been actionable), `EXPIRED` (session/time
boundary), `SUPERSEDED` (a newer Decision/EntryQualification replaced the
one this artifact was bound to). **Missing/stale evidence must never be
collapsed into `INVALIDATED`** — that would silently convert an
evidentiary gap into a false negative signal, exactly the trap ADR-013
already identified and avoided for `EntryQualification`.

## 31. Architecture-vs-methodology separation

**Architectural (freeze-able now, no fitting/tuning required):**
domain-object boundary and identity (§19); persistence conventions (§29);
lifecycle/state-model shape, not its exact enum names (§30); point-in-time
rules and finality independence (§20-21); upstream/downstream ownership
(EntryQualification remains untouched and upstream; ID-9/10/11 remain
strictly downstream consumers, never implemented here).

**Methodology requiring evidence before freezing (explicitly NOT decided
here):** entry trigger selection (§13); maximum qualification/evidence age
before an actionability check is considered stale; acceptable price
displacement from qualification-time price; stop-selection precedence
among the candidates in §14; any ATR fallback multiplier; minimum R:R;
resistance-headroom rule (§15); expiry duration; late-session cutoff
policy. None of these numbers are smuggled into this document's
architectural recommendations.

## 32. Architecture options considered

**Option A — Extend/reuse the existing `TradePlan` representation.**
**Rejected.** `TradePlan` is embedded inside the immutable `Decision`
object with no independent identity or table (§4); it exists **only** for
TRADE-type Decisions, never WATCH (a hard invariant, §4) — yet the
population `EntryQualification` actually evaluates is overwhelmingly WATCH
(6,640/6,640 rows in the ID-6E final audit); and it is computed
synchronously at Decision time from D1 data only, before
`EntryQualification` even runs in the same cycle (§8). Retrofitting it to
consume intraday-actionability evidence would require either making
`Decision` mutable/re-persistable (breaks immutability and replayability),
or attaching a plan to every Decision type (breaks the TRADE-only
invariant), or updating a plan asynchronously after the immutable Decision
row is already persisted (breaks append-only persistence). All three are
architecture violations, not implementation inconveniences.

**Option B — A separate intraday EntryPlan/EntryProposal artifact,
upstream of/orthogonal to the existing TradePlan.** **Recommended.** Bound
to `(decision_id, entry_qualification identity)` exactly as
`EntryQualification` itself is bound to `decision_id` (§19); independent
lifecycle and evidence-finality (§21, §30); can apply to WATCH candidates,
which Option A structurally cannot; leaves the existing swing `TradePlan`/
`DecisionEngine` completely untouched (zero regression risk to the
already-closed, frozen swing methodology); matches ADR-013's own precedent
of building `EntryQualification` as a new orthogonal artifact rather than
folding readiness into `Decision` itself; matches ADR-012's general "new
capability → new isolated boundary, no retrofit contamination" governance
pattern (even though ID-7 is not proposed as isolated as DarvaX/EMR — it
still deliberately avoids touching frozen upstream contracts).

**Option C — An actionability artifact that only references the existing
TradePlan without changing it.** **Rejected as the primary architecture**
(though a narrow "TradePlan freshness re-check" sub-feature could still
exist later): this only makes sense if actionability is always scoped to
TRADE-type Decisions that already have a TradePlan, but §4/§6 show the
dominant population `EntryQualification` evaluates is WATCH, which never
has a TradePlan — restricting to Option C would exclude most of the real
population.

**Option D — another architecture supported by repository evidence.** None
identified that improves on Option B; no evidence surfaced during this
discovery pointed toward a materially different shape.

## 33. Recommended architecture

**Option B**, evaluated against the owner's own criteria:

- **Domain semantics**: clean — a new artifact answering WHEN/WHERE/RISK/
  REWARD, orthogonal to WHAT (Decision) and WHETHER (EntryQualification).
- **Daily-vs-intraday separation**: preserved exactly — swing `TradePlan`
  stays daily/ATR-only; the new artifact is intraday-only.
- **Persistence/auditability/replayability**: follows the ID-6C append-only
  pattern already proven in production.
- **Supersession**: solved by binding to exact `decision_id` +
  EntryQualification identity (§18-19), never "current Decision."
- **API compatibility**: existing `TradePlan`/Decision Brief endpoints and
  UI need zero changes; a new artifact gets its own surface (§28), avoiding
  the confusion risk Option A/C would introduce.
- **Temporal validity**: naturally supports an explicit finality/lifecycle
  model (§21, §30), which Option A's flat 6-hour window does not.
- **Future ID-9/10/11**: a dedicated artifact gives ID-9 clean sizing
  inputs and ID-10 a clean supervision target (§26-27) without
  contaminating canonical Decision/TradePlan semantics.
- **Risk of contaminating canonical Decision semantics**: minimal — Option
  B touches nothing DecisionEngine already owns.

This is a recommendation for owner/ADR ratification, not a self-executed
architecture change — nothing has been built.

## 34. ADR requirement

**A new ADR is recommended**, following the exact precedent ADR-013 itself
states for its own necessity (`docs/adr/ADR-013-...md:26-29`): "introduces
a new persisted decision-relevant concept, a new live workflow stage, and a
new architectural boundary between canonical daily `Decision` and intraday
actionability." ID-7's Option B recommendation meets every one of those
three criteria identically. Per repository convention (`CLAUDE.md:31`,
`ADR-012:16`), this is not optional once the boundary is genuinely new —
and it is. **No ADR has been drafted in this document** — only the
recommendation that one is needed, per the owner's own instruction to
default to "merely recommend" rather than draft one, absent an explicit
documented convention authorizing discovery itself to draft a PROPOSED ADR
(none was found).

## 35. Proposed ID-7 sub-milestones (evidence-derived, not automatically authorized)

Mirroring the exact ID-6 sequence, which is the only precedent in this
repository for building a new intraday-evidence-consuming capability from
scratch:

- **ID-7A0** — ADR proposal for the new EntryPlan/actionability
  architecture boundary (mirrors ID-6A0). Deliverable: a PROPOSED ADR for
  owner review. No code.
- **ID-7A** — Immutable domain contract (state/finality/confirmation-
  analogous dimensions per §21/§30, identity/provenance fields per §19).
  No engine logic, no persistence.
- **ID-7B** — Entry/stop/target methodology research (§13-15, §31) —
  evidence-gathering only, under the same look-ahead safeguards as §37,
  producing a frozen v0 methodology proposal for owner approval (mirrors
  ID-6B/6B.1A/6B.1B).
- **ID-7C** — Deterministic, pure, side-effect-free engine implementing
  the frozen v0 methodology (mirrors ID-6B.2/6B.2A).
- **ID-7D** — Persistence, append-only, Decision+EntryQualification-bound
  identity (mirrors ID-6C/6C.1).
- **ID-7E** — Workflow integration — the exact point where §38 Owner
  Question 2 (synchronous same-cycle vs. asynchronous/on-demand) must be
  resolved before design proceeds (mirrors ID-6D/6D.1).
- **ID-7F** — Replay/shadow validation (mirrors ID-6E and its corrective
  slices).

No sub-milestone is authorized by this discovery. This sequence is a
recommendation only.

## 36. Validation strategy

Separated per instruction:

- **Domain invariant tests**: identity/immutability/binding invariants for
  the new artifact (ID-7A/7D), analogous to ID-6A/6C's own test suites.
- **Deterministic engine tests**: pure-function unit tests for whatever v0
  entry/stop/target methodology ID-7B/7C eventually freezes, analogous to
  `EntryQualificationEngine`'s own tests.
- **Point-in-time replay**: reusing the `ReadOnlyStore`/`candidates_at`
  pattern already proven across ID-6B.1/ID-6E, extended to whatever new
  intraday inputs ID-7B selects — with the same settled-vs-live-provisional
  honesty ID-5B/ID-6E already established.
- **Historical methodology evaluation**: only after ID-7B produces a
  frozen candidate methodology, using the same TRAIN/VALIDATION/CALIBRATION/
  FINAL_TEST discipline already established for EMR (ADR-012's chronological
  partition contract is directly reusable prior art, even though EMR itself
  remains isolated).
- **Shadow/live validation**: mirrors ID-6E's full pattern — bounded
  cutoff, read-only, deterministic digest, mutation-proof.
- **Latency/actionability validation**: a dedicated pass answering whether
  a downstream revalidation using fresher already-available evidence is
  safe (§38 Owner Question 5) — likely needs real stage-level
  instrumentation first, which does not exist today (§10).

No profitability backtest was run in this discovery, per instruction.

## 37. Look-ahead safeguards

Required for any future ID-7B methodology research, explicitly identified
per instruction:

- Never use a settled historical M5 representation as though it were the
  live-provisional value that was actually knowable at the time (the exact
  trap ID-5B already found and ID-6E's own documentation repeatedly warns
  against).
- Never use future high/low to choose a stop or entry level.
- Never compute a resistance/support level from candles that postdate the
  evaluation instant.
- Never select a Decision beyond the replay checkpoint (`ts <= checkpoint`,
  the same rule `ReadOnlyStore.candidates_at` already enforces).
- Never allow future-quote leakage into a point-in-time entry-price
  decision.
- Never select a "future" `EntryQualification` observation relative to the
  entry-evaluation checkpoint being replayed.

## 38. Owner decisions required

Kept deliberately small — only questions genuine source inspection cannot
resolve.

---

**Question 1 — Should ID-7 target closing the ~9-10 minute latency gap, or
only compensate for it?**

*Why it matters*: §10's circumstantial finding points at ingestion as the
likely dominant latency source, but this was derived indirectly (EQ-write
clustering), not from direct stage instrumentation. Reducing the gap
(e.g., batching/parallelizing ingestion) is a materially different, larger
engineering investment than architecturally compensating for it (e.g., a
downstream revalidation step using fresher evidence than the bound
EntryQualification observation).

*Options*: (a) ID-7 scope includes latency reduction as its own
sub-milestone; (b) ID-7 scope is compensation-only (revalidation/freshness
checks), latency reduction deferred to a separate future infra milestone;
(c) defer the decision until §10's evidentiary gap is closed with real
instrumentation (see Question 5).

*Agent recommendation*: (b), gated by (c) — characterize precisely first
(a small, cheap instrumentation pass), then decide reduction-vs-
compensation with real evidence rather than the current circumstantial
inference.

*Consequence of each option*: (a) risks scope creep into an infra
optimization project with different validation needs than an intraday
entry architecture; (b) keeps ID-7 focused but permanently bounds
actionability by whatever the latency turns out to be; (c) delays ID-7A0
slightly but avoids designing against an unproven hypothesis.

---

**Question 2 — Should the future EntryPlan/actionability evaluation run
synchronously in the same cycle as Decision/EntryQualification (as another
`WorkflowStage`, further extending the already ~9-10 minute cycle), or
asynchronously/on-demand (e.g., at API request time, or a separate faster
micro-cycle)?**

*Why it matters*: this is the single architecture-investment tradeoff that
most directly shapes ID-7E's design and cannot be answered from source —
it is a genuine product/engineering policy call.

*Options*: (a) synchronous same-cycle `WorkflowStage`, mirroring
EntryQualification's own integration pattern exactly; (b) asynchronous,
computed on read (API request time), always using the freshest available
evidence at consumption time; (c) a separate, faster, narrower micro-cycle
scoped only to already-QUALIFIED candidates.

*Agent recommendation*: (b) for a first version — it directly addresses
§9's actionability problem (always evaluates against current wall-clock
freshness) without adding to the ~9-10 minute cycle, and it's the smallest
change consistent with Option B's "orthogonal artifact" recommendation.
(a) can be revisited later if evidence shows read-time computation is too
expensive per-request.

*Consequence of each option*: (a) keeps everything cycle-synchronous and
simple to reason about, but inherits and compounds the existing latency;
(b) solves staleness directly but introduces request-time computation cost
and a new kind of point-in-time question (is a read-time computation
"replayable" the same way a persisted cycle observation is?); (c) is a
middle ground but is new scheduling infrastructure ID-7 doesn't currently
need to build.

---

**Question 3 — Should the ID-9 (sizing) / ID-10 (live supervision) / ID-11
(execution quality) boundary assignments be formally ratified as durable
roadmap intent now?**

*Why it matters*: this session's own owner authorization message is the
**first place in this repository's history** these three boundaries are
asserted (confirmed — zero prior mentions found anywhere in `docs/`).
Whether to now persist that intent into `ATHENA_BRIEFING.md`/
`docs/MILESTONES.md` as durable roadmap language, or keep it informal until
each is separately authorized, is a documentation-policy call.

*Options*: (a) ratify now — add a short "future ID-track roadmap intent"
note to `ATHENA_BRIEFING.md`; (b) leave it exactly as informal
conversation-only context, re-stated fresh whenever each of ID-9/10/11 is
actually authorized.

*Agent recommendation*: (b) — per this track's own established discipline
(status documents defer to procedure, not stale forward-looking claims;
`ATHENA_BRIEFING.md` §5 explicitly warns against this) — avoids a future
staleness risk if the boundary assignments are later adjusted before any
of those milestones is actually reached.

*Consequence of each option*: (a) gives future sessions a documented
anchor but risks drift if reality changes before ID-9/10/11 are reached;
(b) keeps documents honest but means this context must be re-supplied by
the owner when each milestone is eventually authorized.

---

**Question 4 — Should the future intraday artifact use naming entirely
distinct from "TradePlan" (e.g. "EntryPlan"/"IntradayEntryProposal") to
avoid confusion with the existing swing TradePlan?**

*Why it matters*: product/UI clarity is a genuine owner call, not
something source inspection resolves — but §28 already shows real
confusion risk if the two concepts share naming on the dashboard.

*Options*: (a) fully distinct naming (e.g. `EntryPlan`); (b) a qualified
variant of "TradePlan" (e.g. `IntradayTradePlan`); (c) no preference,
decide at ID-7A domain-modeling time.

*Agent recommendation*: (a) — the two objects have different identity
models, different lifecycles, and different consumers (swing TradePlan
feeds the existing Decision Brief; a new artifact feeds a yet-undesigned
intraday surface) — sharing "TradePlan" in the name risks exactly the kind
of accidental conflation §28 warns about.

*Consequence of each option*: (a) clearest, costs nothing; (b) preserves a
conceptual link but risks exactly the confusion being guarded against; (c)
defers a cheap decision to a later milestone for no clear benefit.

---

**Question 5 — Should ID-7 wait for dedicated stage-level latency
instrumentation before finalizing its architecture, or proceed with
today's coarse whole-cycle evidence?**

*Why it matters*: §10's finding (ingestion as likely dominant latency
source) is derived circumstantially, not proven. Question 1 and Question 2
both depend materially on how confident we are in that finding.

*Options*: (a) insert a small, narrowly-scoped instrumentation-only
sub-milestone before ID-7A0 (add per-stage wall-clock timing to the
already-defined `WorkflowStage` mechanism, replacing the fake `_MonoClock`
with a real one for this purpose only, then re-run the existing ID-6E-style
read-only characterization against real timing data); (b) proceed directly
to ID-7A0 using today's circumstantial evidence, revisiting if it turns out
wrong.

*Agent recommendation*: (a) — this is a small, low-risk, read-adjacent
change (the `WorkflowEngine` timing mechanism already exists at
`runtime/workflow.py:146-181`; only the clock needs to become real), and
it directly de-risks Questions 1 and 2 before committing to an ADR.

*Consequence of each option*: (a) adds one small milestone and a short
delay but grounds Questions 1/2 in proof rather than inference; (b) moves
faster but risks designing ID-7E's synchronicity/latency-response strategy
around an unproven hypothesis.

## 39. Risks

- **Scope creep into latency-reduction infrastructure work** if Question 1
  is resolved toward (a) without careful boundary-setting.
- **Re-deriving EntryQualification's own formula downstream** by accident,
  if a future revalidation step is designed carelessly (explicitly warned
  against in the owner's own authorization, §7 of that message).
- **Boolean collapse** (`if QUALIFIED: BUY`) if ID-7A's domain model is
  designed without the multi-dimension discipline ADR-013 already proved
  necessary for a structurally similar problem.
- **Confusing daily and intraday plans in the UI** if Option B's artifact
  reuses TradePlan-adjacent naming or rendering paths without deliberate
  separation (§28, Question 4).
- **Building on an unproven latency hypothesis** (§10, Question 5) if
  ID-7E's synchronicity design proceeds before the ingestion-vs-compute
  question is confirmed with real instrumentation.
- **No support/resistance methodology exists yet** (§15) — target/reward
  feasibility (the owner's own stated concern) cannot be solved by
  architecture alone; it is a real, unstarted methodology-research gap.

## 40. Final recommendation

Proceed with **Option B** (a new, separate, `Decision`+`EntryQualification`-
bound intraday actionability artifact, architecturally orthogonal to the
existing daily `TradePlan`) as the recommended direction for a future
ID-7A0 ADR proposal — pending owner resolution of the five questions in
§38, particularly Question 5 (instrumentation) and Question 2
(synchronous-vs-asynchronous evaluation), both of which materially shape
what ID-7A0's ADR draft should actually propose. No implementation is
recommended to start immediately; the smallest safe next step, if the
owner agrees with this direction, is **ID-7A0** — an ADR proposal only, no
code — optionally preceded by the narrow instrumentation slice in Question
5 if the owner wants Questions 1/2 de-risked first.
