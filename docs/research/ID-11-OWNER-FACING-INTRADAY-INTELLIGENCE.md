# ID-11 — Owner-Facing Intraday Intelligence Integration

**Status:** OWNER APPROVED / DESIGN FROZEN
**Owner freeze date:** 2026-09-09
**Milestone:** ID-11
**Predecessors:** ID-6 through ID-10, all OWNER APPROVED / CLOSED
**Scope:** Owner-facing exposure/integration only — no new methodology
**Schema migration:** NOT REQUIRED
**Methodology change:** NOT REQUIRED
**Direction:** `LONG_VALIDATED_SHORT_UNVALIDATED` (unchanged)
**Implementation status:** NOT STARTED — this document is the frozen design
contract implementation must follow; it is not itself an implementation.

This document is the single canonical source of truth for ID-11. It
consolidates the ID-6→ID-10 Owner/UI Exposure Audit, the ID-11 Discovery +
Design Contract, and two source-verification correction rounds, all
conducted and Owner-reviewed on 2026-09-09. It supersedes nothing about the
frozen ID-6→ID-10 methodology or engines — it only defines how their
already-computed outputs reach the Owner.

---

## 1. Why ID-11 exists

A source-backed ID-6→ID-10 Owner/UI Exposure Audit (2026-09-09) traced every
completed Intraday Intelligence capability from domain computation through
persistence, API, and dashboard rendering, citing exact file/function/line
evidence at every layer. Findings:

| Capability | Classification |
|---|---|
| ID-6 EntryQualification | `PARTIALLY_EXPOSED` — one binary tooltip string (My Portfolio's ADD-reason hover text), for the QUALIFIED state only; no evidence, no reason breakdown for other states, no freshness display |
| ID-7 EntryActionability | `BACKEND_ONLY` — fully computed and persisted, zero API/DTO/dashboard reference |
| ID-8 Entry/Risk methodology | `RESEARCH_ONLY_NOT_FOR_UI`, except the narrow production concepts (VWAP-loss invalidation, T1/T2 goal bands, risk geometry) already absorbed into ID-7's frozen contract |
| ID-9 PositionSizing | `BACKEND_ONLY` / `GENUINE_OWNER_UI_GAP` — a live, policy-bound quantity recommendation computes every cycle and is never seen |
| ID-10 LivePlanSupervision | `BACKEND_ONLY` / `GENUINE_OWNER_UI_GAP` — the live VALID/INVALIDATED verdict is discarded at the end of every cycle |

**Precise framing (Owner-mandated correction — do not restate this any other
way):** ID-11 exists because a genuine, source-proven Owner-facing exposure
gap was found across ID-7/ID-9/ID-10 (and a near-total one for ID-6) — not
because the newer Intraday Intelligence pipeline is universally superior to
the legacy `TradePlan`. Each ID-track milestone retains its own accepted
empirical classification. In particular:

> ID-8 remains `ID8_V0_ENTRY_RISK_PARTIALLY_SUPPORTED`. No claim of
> guaranteed 1–1.5% moves. No research diagnostic from ID-8 (MFE/MAE
> studies, bootstrap intervals, PR-AUC, validation tables, hit-rate tables,
> session-fold statistics) may ever appear in the Owner-facing UI.

The full audit trail lives only in this conversation's own record (no
separate audit document was created, per the Owner's own discovery-phase
instruction not to create sub-milestone documents); this document freezes
only its accepted conclusions and the resulting design.

---

## 2. Structural Plan vs. Intraday Plan

The audit proved the existing Decision Brief's `TradePlan`-derived UI (My
Portfolio's "Plan Levels", the Decision Brief's "Advisor status"/"entry
readiness") is a **completely separate system** from the ID-6→ID-10 chain —
confirmed by direct source inspection with zero shared code path
(`decision/engine.py::_build_plan` never references `entry_actionability`;
`13-decision-brief-core.js`'s actionability banner reads only
`decision.trade_plan`).

| | **STRUCTURAL PLAN** | **INTRADAY PLAN** |
|---|---|---|
| Source | Existing canonical `Decision.trade_plan` (`domain/decision.py::TradePlan`) | `EntryQualification` → `EntryActionability` → `PositionSizing` → `LivePlanSupervision` |
| Basis | Daily, D1 ATR/SMA-derived | Intraday, VWAP/M5-anchored, checkpoint-fresh |
| Question answered | "What does the daily structural context suggest?" | "Is entry actionable right now, intraday?" |
| Lifecycle | Unchanged by ID-11 | New, this milestone |

**Both may legitimately be valid, simultaneously, for the same Decision.**
Neither is authoritative over the other; they answer different questions.
ID-11 does **not** replace `TradePlan`, does **not** merge the two
methodologies, and does **not** mutate `TradePlan` in any way.

### Presentation naming cleanup (terminology only — no domain object renamed)

| Existing label | Real meaning (source-confirmed) | Corrected label |
|---|---|---|
| "Advisor status" / `#decision-actionability-banner` (`13-decision-brief-core.js:653`) | Legacy `TradePlan` freshness (EXPIRED/STALE/AGING/FRESH) | **Structural Plan Status** |
| "Entry readiness" badge (`13-decision-brief-core.js:110`) | Legacy `TradePlan` entry-zone vs. quote | **Structural Entry Zone** |
| "Plan freshness" (`05-utils.js`, `/plan-freshness` route) | `TradePlan` time-decay | **Structural plan freshness** |
| My Portfolio "Plan Levels" column | Already self-documented in-UI as `TradePlan`-only | May be relabeled **Structural Plan Levels** for symmetry; Portfolio methodology itself is unchanged |
| *(new)* | ID-11's own qualification/actionability/sizing/supervision freshness | **Intraday freshness / currentness** — never the bare word "freshness" alone in either section |

---

## 3. Canonical API identity

**Anchor: `decision_id`, alone.**

- `Decision.decision_id` is a globally unique, persisted primary identity —
  schema declares `decision_id TEXT PRIMARY KEY` (`schema.py:214-215`);
  `SqliteRepository.get_decision(decision_id)` fetches by this key alone,
  with no other disambiguating parameter.
- Instrument-only identity is explicitly rejected as an anchor — it could
  ambiguously bind to the wrong historical Decision for the same
  instrument.

### Endpoint

```
GET /api/v1/decisions/{decision_id}/intraday-intelligence
```

A new sibling route inside the existing `src/athena/api/v1/routers/decisions.py`,
following the exact established "Decision detail, without recomputation"
pattern already used by `/depth`, `/counterfactual`, `/plan-freshness`,
`/context`, `/trace`.

**Properties (all frozen):**
- Read-only.
- Decision-anchored.
- One response contains the whole coherent chain.
- No writes.
- No hidden full validation cycle — never invokes `DecisionEngine`,
  `ScoringEngine`, `ConfidenceEngine`, `RiskEngine`, or
  `OwnerValidationPipeline`. The existing `GET /decisions/{decision_id}`
  route already proves this exact "cheap read-only lookup by id" pattern
  is standard in this codebase (`decisions.py:164-191` →
  `decisions_service.py:170-175` → `sqlite_providers.py:150-151` →
  `repository.py:1050-1057`, a single `SELECT`).
- No persistence added merely for presentation.

---

## 4. EntryQualification coherence contract

**Terminology, frozen precisely: EntryQualification COHERENCE, not
EntryQualification currentness.** No age-based staleness threshold exists
for EQ anywhere in frozen methodology, and none is invented here.

The only existing related logic is `portfolio/sync.py::_latest_coherent_entry_qualification`
(lines 644-672) plus its precondition `_decision_matches_price_session`
(lines 613-625). Source review found the precondition compares a Decision's
timestamp against a **Portfolio-holding-specific `price_as_of`** (a
holding's own D1 candle timestamp) — genuinely Portfolio-specific
reconciliation logic that does **not** belong in the general EQ contract,
since ID-11 resolves its Decision directly by `decision_id` and has no
separate "holding price" to reconcile against.

### Frozen helper

```
resolve_entry_qualification_coherence(
    eq: EntryQualification | None,
    decision: Decision,
    read_checkpoint: datetime,
    market_timezone: tzinfo,
) -> EntryQualificationCoherence   # COHERENT | INCOHERENT
```

This is **semantics extraction from already-Owner-approved Portfolio code**,
not new methodology.

**EQ row selection:** `self._repo.latest_entry_qualification_for_decision(decision.decision_id)`
— the same repository method `sync.py` itself uses, keyed on the
already-resolved canonical `decision_id`.

**Deterministic checks, exact frozen order:**

1. EQ exists (else `INCOHERENT`).
2. Instrument identity matches Decision.
3. `decision_id` matches.
4. `run_id`/`cycle_id` match.
5. `decision_type` matches.
6. `eq.session_date` matches the read-checkpoint's own session date.
7. `eq.as_of`'s market-local date matches that same session date.
8. `eq.as_of <= read_checkpoint` (point-in-time / not-future check).

**Read checkpoint:** the endpoint's own injected `now` (read-time wall
clock, per ATHENA's determinism invariant) — never a Portfolio-specific
`expected_analysis_as_of`/`price_as_of` fallback chain, since neither
concept exists in the ID-11 context.

**Session date:** `read_checkpoint.astimezone(market_timezone).date()`.

**Result states:** exactly two — `COHERENT` / `INCOHERENT` — matching what
the source itself returns (`eq` or `None`, never a graded staleness). An
`explanation: str` may describe which check failed (diagnostic text, not a
new enum).

**Feeding `EntryActionabilityIdentity`:** only when `COHERENT`, populate
`EntryQualificationIdentity(instrument_id=eq.instrument_id, session_date=eq.session_date,
as_of=eq.as_of, decision_id=eq.decision_id, methodology_version=eq.methodology_version)`
directly from the resolved EQ row's own fields — mirroring
`owner_validation.py:1658-1664`'s existing production pattern exactly. If
`INCOHERENT`, the endpoint does not proceed to EntryActionability
currentness at all (§9).

---

## 5. EntryActionability currentness contract

**Reuse `entry_actionability_currentness.is_currently_usable(...)` verbatim
— no UI/API-specific substitute is permitted, ever.**

Frozen result states (ID-7A.2 contract, unchanged):

```
CURRENT | STALE | SUPERSEDED | SESSION_CLOSED | METHODOLOGY_NOT_ACTIONABLE
```

Checked in the frozen order: input validation → temporal-impossibility →
`METHODOLOGY_NOT_ACTIONABLE` → Decision mismatch → EQ mismatch → `STALE` →
`SESSION_CLOSED` → `CURRENT`; either identity mismatch (Decision or EQ)
yields the same `SUPERSEDED` derivation.

**A persisted `EntryActionability.state == ACTIONABLE` must never be read
directly as "currently actionable."** Currentness must always be evaluated
at read time against: the current Decision's identity, the current
`COHERENT` EQ's identity (§4), the current session phase, and the injected
`now`. `is_currently_usable`'s own inputs are all identity/clock/session-phase
values — it performs zero repository or provider calls internally.

---

## 6. PositionSizing read-time contract (ID-9)

> **ID-9 POSITION SIZING REQUIRES ZERO FRESH MARKET-EVIDENCE FETCH.**

Source-proven directly from `PositionSizingV0Engine.evaluate`
(`position_sizing_engine.py:93-101`) — its signature takes no market-evidence
parameter at all, and a full-file review confirms zero
`Candle`/`vwap`/`OpeningRange`/`get_candles`/repository/provider reference
anywhere in the module. Exact read-time dependencies:

1. The persisted/current `EntryActionability` row (already contains
   entry/invalidation/T1/T2/direction).
2. The `EntryActionabilityCurrentness` result from §5.
3. Canonical instrument `lot_size` — non-market, instrument-catalog
   metadata (see §9 for exact failure semantics).
4. The loaded `CapitalPolicy`.

No M5 fetch, no VWAP fetch, no OR15 fetch, no quote fetch is required to
recompute `PositionSizing`.

`PositionSizing` remains **derived-only, no persistence**. The existing
`PositionSizingV0Engine` remains completely unchanged. Future
implementation must extract one shared composition function
(`compose_position_sizing(...)`) from the existing `position_sizing_stage`
(`owner_validation.py:1585-1687`), reused identically by the production
`WorkflowStage` and the new ID-11 read service — no duplicate sizing
mathematics, no parallel reimplementation.

---

## 7. LivePlanSupervision read-time contract (ID-10)

`LivePlanSupervision` remains **derived-only, no persistence, no persisted
FSM**. The existing `LivePlanSupervisionEngine` remains completely
unchanged.

**Candle source window (frozen, session-bounded — not unbounded):**

```
canonical session start  →  current supervision checkpoint
```

Source-confirmed: `owner_validation.py:1816-1819` calls
`self._repo.get_candles(instrument_id, Timeframe.M5, session_day_start(ctx.as_of, session_tzinfo), ctx.as_of)`
— identical in shape to the existing VWAP evidence fetch elsewhere in the
same stage. This is a plain local SQLite read (`repository.py:573-582`,
confirmed zero provider/network call) — cheap, bounded to ≤75 M5 rows per
session.

**Supervision event sub-window**, within that already session-bounded
history:

```
EntryActionability.evidence_as_of  →  current supervision checkpoint
```

**Preserve exactly, unchanged:**
- The frozen two-window contract: `session_completed_m5` (VWAP source
  window) is never substituted for `supervised_path` (supervision event
  window) — conflating them was an already-corrected prior defect.
- Evolving session-cumulative VWAP recomputed at each checkpoint.
- First-chronological VWAP-loss trigger semantics.
- Permanent invalidation for a given EA identity, achieved purely by
  deterministic re-evaluation of the full event window every call — no
  persisted state machine, no flag.
- Target progress is informational only.
- `supervision_as_of` is distinct from `evaluated_at`, and both are
  distinct from `entry_actionability.entry_actionability_as_of`.
- Gate order A→E: upstream not ACTIONABLE → direction not LONG →
  currentness not CURRENT → VWAP-loss triggered → else VALID.
- `VWAP_LOSS` remains the sole V0 market-invalidation trigger.

**No arbitrary N-candle lookback is ever introduced** — the bound is the
session boundary itself, a source-backed semantic quantity, never a
performance guess. No Kite/provider request is introduced merely for Owner
UI exposure.

Future implementation must extract one shared composition function
(`compose_live_plan_supervision(...)`) from the existing
`live_plan_supervision_stage` (`owner_validation.py:1689-1847`), reused
identically by the production stage and the ID-11 read service.

---

## 8. Downstream non-current-EA semantics (frozen, corrected)

Source-verified directly against both engines' full source:

| EA currentness (§5) | `PositionSizingV0Engine` output | `LivePlanSupervisionEngine` output |
|---|---|---|
| `CURRENT` | Proceeds to real sizing math | Proceeds to real VWAP-loss/target evaluation |
| `STALE` / `SUPERSEDED` / `SESSION_CLOSED` | **`NOT_SIZED`, reason `UPSTREAM_NOT_CURRENT`** (`position_sizing_engine.py:215-228`) | **`NOT_APPLICABLE`, reason `UPSTREAM_NOT_CURRENT`** (`live_plan_supervision_engine.py:297-310`) |

**These are legitimate, deterministic engine verdicts and must never be
converted to `UNAVAILABLE`.** The read model passes through exactly what
the engines return.

### Frozen state-meaning distinctions

- **`NOT_SIZED`** — the engine successfully evaluated and intentionally
  refused sizing (reasons include `UPSTREAM_NOT_ACTIONABLE`,
  `UNVALIDATED_DIRECTION`, `UPSTREAM_NOT_CURRENT`, `CAPITAL_POLICY_UNAVAILABLE`,
  `INVALID_RISK_GEOMETRY`).
- **`NOT_APPLICABLE`** — the engine successfully evaluated and supervision
  does not apply (reasons include `UPSTREAM_NOT_ACTIONABLE`,
  `UNVALIDATED_DIRECTION`, `UPSTREAM_NOT_CURRENT`).
- **`UNAVAILABLE`** — the read model genuinely cannot obtain/derive the
  required input at all (no EQ row, EQ `INCOHERENT`, no EA row, a canonical
  instrument/lot-size invariant is broken — see §9). Reserved strictly for
  this case; never used for a value an engine actually computed.
- **`INVALIDATED`** — real market invalidation occurred (VWAP-loss
  triggered).

---

## 9. API failure semantics

Source-confirmed existing convention (`src/athena/api/errors.py`,
`AthenaExceptionMapper`; `src/athena/api/app.py`'s global exception
handlers, both wired and unchanged):

```
DecisionNotFoundError -> 404
ValueError             -> 400
ProviderError          -> 502
RepositoryError        -> 503
AthenaError             -> 500   (base-class catch-all)
unexpected Exception    -> 500
```

### Frozen rule (single deterministic contract — no fork)

- **Expected domain absence/non-applicability → HTTP 200 + typed DTO
  state.** Examples: no EQ, EQ `INCOHERENT`, no EA, `NOT_ACTIONABLE`,
  non-current EA (§8), SHORT/`UNVALIDATED_DIRECTION`,
  `CapitalPolicy` absent — every one of these is a real, deterministic
  outcome an existing frozen engine (or the new coherence helper) already
  knows how to express.
- **Unexpected infrastructure/invariant failure → Problem Details / the
  existing 5xx path.** Never converted into `NOT_ACTIONABLE`,
  `NOT_APPLICABLE`, or `UNAVAILABLE`.

### Frozen lot-size/instrument-invariant boundary (fully deterministic — no ambiguity)

Production (`position_sizing_stage`, `owner_validation.py:1608-1629`)
resolves `lot_size` from an **in-memory dict** already built earlier in
that scan (`instrument_by_id.get(instrument_id)`) and raises a bare
`ValueError` if the instrument is missing or `lot_size < 1` — this
production-workflow behavior is **left completely unchanged**. The ID-11
read endpoint has no live scan to draw from and must perform a **direct
instrument-catalog/repository read** instead. Frozen mapping for the read
path:

| Case | Exception that escapes the ID-11 service | HTTP status |
|---|---|---|
| Repository/instrument-catalog access itself fails (DB error) | `RepositoryError` (existing convention, unchanged) | **503** |
| Repository read succeeds; instrument not found in the canonical catalog | ID-11's application boundary catches this and raises the base `AthenaError` (translation *only* at this boundary — no new exception subclass, no global `AthenaExceptionMapper` change) | **500** |
| Instrument exists but `lot_size` is absent/invalid | Same translation: `AthenaError` raised at the ID-11 boundary | **500** |
| `decision_id` does not resolve to a real Decision | `DecisionNotFoundError` (mirrors the existing `/decisions/{decision_id}` precedent) | **404** |

This endpoint has no legitimate client-input `ValueError`/400 case — its
only input is the path-anchored `decision_id`, and an unresolvable one is a
404, not a 400. The global `ValueError → 400` handler is unchanged and
remains correct for the rest of the application; it is simply not exercised
by this route's own designed failure modes. `AthenaExceptionMapper` is
**not** changed globally for ID-11.

---

## 10. Owner read model — `IntradayIntelligenceDTO`

Pydantic `BaseModel`, `ConfigDict(frozen=True)`, following the existing
house style (`api/v1/dtos/decisions.py`, `dtos/dashboard.py`'s
`Literal[...]` + `"UNAVAILABLE"` pattern).

```
IntradayIntelligenceDTO:
  identity: { decision_id, instrument_id, decision_type, direction,
              session_date, run_id, cycle_id,
              eq_methodology_version, ea_methodology_version }

  qualification: { state: Literal[EQ states + "UNAVAILABLE"],
                    coherence: Literal["COHERENT","INCOHERENT","UNAVAILABLE"],
                    reason_summary: str | None,
                    evidence_summary: str | None,
                    evidence_as_of: datetime | None }

  actionability: { state: Literal[EA states + "UNAVAILABLE"],
                    reason: str | None,
                    entry_reference: Decimal | None,
                    operative_invalidation: {...} | None,
                    t1: Decimal | None, t2: Decimal | None,
                    reward_risk_informational: Decimal | None,
                    evidence_as_of, entry_actionability_as_of,
                    currentness: Literal["CURRENT","STALE","SUPERSEDED",
                                          "SESSION_CLOSED",
                                          "METHODOLOGY_NOT_ACTIONABLE",
                                          "UNAVAILABLE"] }

  sizing: { state: Literal["SIZED","NOT_SIZED","ZERO_QUANTITY_UNDER_POLICY","UNAVAILABLE"],
            reason: str | None,
            suggested_quantity: int | None,
            lot_size: int | None,
            binding_constraint: str | None,
            policy_version: str | None }
            # total_deployable_capital / per-share risk amount / position
            # value are OMITTED from the default payload -- see S11.

  supervision: { state: Literal["NOT_APPLICABLE","VALID","INVALIDATED","UNAVAILABLE"],
                 reason: str | None,
                 target_progress: Literal["NONE_REACHED","T1_REACHED",
                                            "T2_REACHED","UNAVAILABLE"],
                 vwap_loss_evidence: {...} | None,
                 supervision_as_of, evaluated_at }

  as_of_summary: { computed_at: datetime, freshest_evidence_as_of: datetime | None }
```

No irrelevant research field (MFE/MAE, bootstrap, PR-AUC, etc.) appears
anywhere. Missing values render semantically as `—` / "Not available" /
"Not applicable" / "Unvalidated direction" — never a fabricated zero.

---

## 11. Privacy

Reuse the existing My Portfolio privacy convention
(`08b-my-portfolio.js`: `myPortfolioMaskedValue()`, `valuesHidden` gate,
`renderMyPortfolioPrivacyToggle()`, `myPortfolioPrivateHtml()`).

**`total_deployable_capital` is never exposed by default** — it is not
needed to explain a suggested quantity. The minimal Owner sizing
presentation is: **Suggested Qty**, **Binding Constraint** (name only, e.g.
`"MAX_POSITION_VALUE"`), **Policy version** (if useful). Any future need to
show `theoretical_risk_amount`/estimated rupee risk must go through the
same masking convention as My Portfolio's money fields. No unnecessary
disclosure of `CapitalPolicy` internals.

---

## 12. SHORT-direction behavior

Direction remains `LONG_VALIDATED_SHORT_UNVALIDATED`. For SHORT: no
fabricated LONG-derived guidance, no silent pretense of support. Owner
presentation communicates explicitly:

> Intraday V0: Short direction not yet validated

while preserving the exact frozen engine outcomes: `sizing.state =
"NOT_SIZED"`, `reason = "UNVALIDATED_DIRECTION"`; `supervision.state =
"NOT_APPLICABLE"`, `reason = "UNVALIDATED_DIRECTION"` — both real,
already-existing gates in the two engines (§8), never `UNAVAILABLE`.

---

## 13. ID-8 boundary

ID-8 itself receives **no UI**. Preserve `ID8_V0_ENTRY_RISK_PARTIALLY_SUPPORTED`
verbatim. Never expose MFE/MAE studies, bootstrap confidence intervals,
PR-AUC, validation tables, historical hit-rate tables, or session-fold
diagnostics. Only production concepts already absorbed into the frozen
runtime contract may appear: VWAP-loss invalidation, T1/T2, risk geometry —
these are already covered as ordinary `EntryActionability` fields (§10), not
a separate "ID-8 section." No claim of guaranteed 1–1.5% movement, anywhere.

---

## 14. Owner UI information architecture

Inside the existing Decision Brief, add one new **"Intraday Plan"** section,
clearly separated from the existing **"Structural Plan"** section (§2):

```
STRUCTURAL PLAN                     INTRADAY PLAN
(existing, relabeled per S2)        (new, this milestone)

Plan Trigger / Stop / T1            QUALIFICATION
Structural plan freshness             Qualified / Waiting / Not available
                                     ENTRY
                                       Actionable / Not actionable / Not available
                                       Entry ₹— · Invalidation ₹— · T1 ₹— · T2 ₹—
                                     SIZE
                                       Suggested Qty — · Limited by —
                                     LIVE STATUS
                                       VALID / INVALIDATED / Not applicable
                                       Target: None reached / T1 reached / T2 reached
                                     As of hh:mm · [Current / Stale / Superseded / Session closed]
```

**One coherent surface — not five separate ID-6/7/8/9/10 panels.** The
Owner should be able to understand, in one glanceable place:

- **WHAT** — Decision / qualification
- **WHETHER** — actionability
- **WHEN/WHERE** — entry, invalidation, targets
- **HOW MUCH** — theoretical sizing
- **DOES IT STILL HOLD** — live supervision

---

## 15. Shared-composition implementation intent (not implemented yet)

Planned, reusable pieces for the future implementation milestone:

1. `resolve_entry_qualification_coherence(...)` (§4) — new, extracted from
   `sync.py:658-670`'s coherence checks.
2. `compose_position_sizing(...)` (§6) — extracted from `position_sizing_stage`
   (`owner_validation.py:1585-1687`), calling `PositionSizingV0Engine.evaluate`
   unchanged.
3. `compose_live_plan_supervision(...)` (§7) — extracted from
   `live_plan_supervision_stage` (`owner_validation.py:1689-1847`), calling
   `LivePlanSupervisionEngine.evaluate` unchanged.

Both the production `WorkflowStage`s and the new ID-11 read service must
call the same extracted functions — **no duplicate sizing/supervision
mathematics, no parallel reimplementation, no frozen-engine change of any
kind.**

---

## 16. Test contract (for the future implementation milestone)

1. ACTIONABLE current LONG → full chain composes correctly end-to-end.
2. Superseded EA → `actionability.currentness != CURRENT`; `sizing.state ==
   "NOT_SIZED"`/`reason == "UPSTREAM_NOT_CURRENT"`; `supervision.state ==
   "NOT_APPLICABLE"`/`reason == "UPSTREAM_NOT_CURRENT"` (never `UNAVAILABLE`).
3. Session-closed EA → identical corrected assertions as #2 for
   `SESSION_CLOSED`.
4. WATCH-bound `NOT_ACTIONABLE` renders its true reason, never hidden.
5. SHORT renders `UNVALIDATED_DIRECTION` on both sizing and supervision — no
   fabricated values.
6. `compose_position_sizing` and the production `position_sizing_stage`
   produce byte-identical results for identical inputs.
7. `compose_live_plan_supervision` and the production
   `live_plan_supervision_stage` produce byte-identical results.
8. A VWAP-loss trigger for a given EA identity remains `INVALIDATED` after a
   later re-query following price recovery (permanence proof).
9. T1/T2 `target_progress` recomputes identically across two independent
   calls with identical inputs (determinism proof).
10. The endpoint's handler never calls any `save_*` repository method
    (call-count spy).
11. The endpoint never imports/calls `DecisionEngine`/`ScoringEngine`/
    `ConfidenceEngine`/`RiskEngine`/`OwnerValidationPipeline` (source-scan
    proof).
12. Missing artifacts (no EQ, EQ `INCOHERENT`, no EA) render typed
    `"UNAVAILABLE"`, never `0`/blank.
13. Privacy masking: `total_deployable_capital` never appears in the
    default payload; any future masked field reuses the My Portfolio
    convention correctly.
14. Legacy `TradePlan` rendering is provably unchanged (existing Decision
    Brief tests continue to pass unmodified).
15. Generated OpenAPI schema covers every new DTO `Literal` state, including
    every `"UNAVAILABLE"` variant.
16. Dashboard JS has explicit rendering tests for each state of each of
    qualification/actionability/sizing/supervision.
17. `resolve_entry_qualification_coherence` individually tests each of the
    8 checks in §4, both pass and fail.
18. Infrastructure-error status assertions: a forced `RepositoryError` → 503
    Problem Details; a forced missing-instrument/invalid-lot_size condition
    → 500 Problem Details (not 400); an unresolvable `decision_id` → 404.
    All three additionally assert the response body is a Problem Details
    error object, never a 200 with a domain-state field.

**All existing ID-6/7/9/10 domain, engine, currentness, and
workflow-integration tests must continue passing unchanged** — the
extractions in §15 must be proven behavior-preserving against them exactly
as ID-7E's/ID-9's own extractions were.

---

## 17. Explicit non-goals

No broker/order/execution integration, ever. No `DecisionEngine`/`Scoring`/
`Confidence`/`Risk` mutation. No reopening of ID-8's research findings into
production. No new entry/risk/sizing/supervision methodology or threshold.
No `PositionSizing`/`LivePlanSupervision` persistence. No schema migration.
No SHORT methodology invention. No synthetic/fabricated values. No EMR
changes (isolated, natural accumulation continues untouched). No DarvaX
changes. No Portfolio methodology mutation (Status/Conviction/D1
Trend/Setup/Daily Review/EXIT_RISK all remain exactly as frozen). No
caching (none is required — every read is a cheap local recompute; see
§6/§7's cost analysis). No global change to `AthenaExceptionMapper`.

---

## 18. File/function-level implementation map (for the future milestone)

- **New**: `src/athena/intraday/entry_qualification_coherence.py` —
  `resolve_entry_qualification_coherence(...)`.
- **New**: a composition module housing `compose_position_sizing(...)` and
  `compose_live_plan_supervision(...)`, extracted from
  `owner_validation.py:1585-1687` / `:1689-1847`.
- **Modified (call-site only, no logic change)**: `owner_validation.py`'s
  `position_sizing_stage`/`live_plan_supervision_stage` to call the
  extracted functions.
- **New**: `src/athena/api/v1/dtos/intraday_intelligence.py` —
  `IntradayIntelligenceDTO` and nested DTOs (§10).
- **New**: a service/provider pair mirroring `decisions_service.py`/
  `sqlite_providers.py`'s existing pattern.
- **Modified**: `src/athena/api/v1/routers/decisions.py` — new
  `GET /{decision_id}/intraday-intelligence` route.
- **Modified (presentation only)**: `13-decision-brief-core.js` (label text
  per §2), plus a new rendering module for the Intraday Plan section.
- **Unchanged**: every domain model, every engine (`entry_qualification_engine.py`,
  `entry_actionability_engine.py`, `position_sizing_engine.py`,
  `live_plan_supervision_engine.py`), `schema.py`, `repository.py`'s
  existing write paths, `AthenaExceptionMapper`.

---

## 19. Schema migration / methodology change

**Schema migration: NOT REQUIRED.** `EntryQualification`/`EntryActionability`
are already persisted under schema v18 (unchanged). `PositionSizing`/
`LivePlanSupervision` remain derived-only.

**Methodology change: NOT REQUIRED.** Every engine is called unchanged. The
one new piece of logic (`resolve_entry_qualification_coherence`) is
semantics extraction from already-Owner-approved Portfolio code, not a new
methodology — no new threshold, no new formula, no new gate.

---

## 20. Final classification

`ID11_DESIGN_OWNER_APPROVED_FROZEN — 2026-09-09 — IMPLEMENTATION NOT STARTED`
