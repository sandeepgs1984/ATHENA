# ID-11 — Owner-Facing Intraday Intelligence Integration

**Status:** IMPLEMENTED — READY FOR OWNER / CHIEF ARCHITECT REVIEW (design was OWNER APPROVED / DESIGN FROZEN 2026-09-09)
**Owner freeze date:** 2026-09-09
**Implementation date:** 2026-09-09
**Milestone:** ID-11
**Predecessors:** ID-6 through ID-10, all OWNER APPROVED / CLOSED
**Scope:** Owner-facing exposure/integration only — no new methodology
**Schema migration:** NOT REQUIRED (confirmed — none performed)
**Methodology change:** NOT REQUIRED (confirmed — both frozen engines called unchanged)
**Direction:** `LONG_VALIDATED_SHORT_UNVALIDATED` (unchanged)
**Implementation status:** IMPLEMENTED, full test suite green (4011 passed / 1
pre-existing unrelated skip / 0 failures), source-reviewed against every item
in this document's own frozen contract. **Not marked OWNER APPROVED / CLOSED
/ FROZEN — awaiting Owner/Chief Architect source review.** See §21
"Implementation Result" at the end of this document for the full record.

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

## 20. Final classification (design)

`ID11_DESIGN_OWNER_APPROVED_FROZEN — 2026-09-09 — IMPLEMENTATION NOT STARTED`

---

## 21. Implementation result (2026-09-09)

Implemented as one milestone, exactly as frozen above — no sub-milestone
created. Every contradiction check against current source found zero
conflicts with this document; nothing here was revised during
implementation.

**Files created:**
- `src/athena/intraday/entry_qualification_coherence.py` —
  `resolve_entry_qualification_coherence(...)` per §4, verbatim.
- `src/athena/intraday/intraday_composition.py` — `compose_position_sizing(...)`
  and `compose_live_plan_supervision(...)`, extracted from the production
  stages exactly as specified in §6/§7/§15.
- `src/athena/api/v1/dtos/intraday_intelligence.py` — `IntradayIntelligenceDTO`
  and nested DTOs, matching §10 exactly (renamed `coherence`/`currentness`
  fields as designed; `total_deployable_capital` absent).
- `tests/market_intel/test_entry_qualification_coherence.py` (13 tests),
  `tests/market_intel/test_intraday_composition.py` (7 tests),
  `tests/api/v1/test_decision_intraday_intelligence.py` (7 HTTP integration
  tests).

**Files modified:**
- `src/athena/ops/owner_validation.py` — `position_sizing_stage`/
  `live_plan_supervision_stage` bodies replaced with calls to the extracted
  composition functions (call-site only; both frozen engines and all other
  stage logic byte-for-byte unchanged; full pre-existing `test_owner_validation.py`
  suite — 92 tests — passes unchanged, proving behavior preservation).
- `src/athena/api/v1/services/decisions_service.py` — new
  `get_intraday_intelligence(decision_id)` method, per §3-§9 (originally
  implemented as `get_intraday_intelligence(decision_id, *, as_of=None)`;
  the public `as_of` parameter was removed same-week by the §22
  source-review correction below — see §22 for why).
- `src/athena/api/v1/routers/decisions.py` — new
  `GET /{decision_id}/intraday-intelligence` route, sibling to
  `/plan-freshness`, identical pattern.
- `src/athena/api/v1/dtos/__init__.py` — new DTO exports.
- `src/athena/api/app.py` — new `DASHBOARD_JS_PARTS` entry
  (`19b-decision-brief-intraday.js`, inserted between `19-decision-brief-history.js`
  and `20-operations.js`, mirroring the existing `08b`/`09b` insertion
  convention — no renumbering of existing files).
- `src/athena/api/static/index.html` — new "Intraday Plan" card (§14);
  presentation-only label/aria-label additions for the three naming-cleanup
  rows (§2); dashboard asset version bumped `9.204.0` → `9.205.0`.
- `src/athena/api/static/js/13-decision-brief-core.js` — three label renames
  ("Advisor status" → "Structural Plan Status"; the Quick Summary "Plan
  Status" row → "Structural Plan Freshness"); one new call site
  (`loadIntradayPlan(meta.decision_id)` alongside the other per-decision
  `load*` calls); one new reset call site (`resetIntradayPlanCard()`
  alongside `renderDecisionBriefEmpty`'s other resets).
- `src/athena/api/static/dashboard.css` — new `@import` for
  `css/14-intraday-plan.css`.
- `docs/api/openapi.yaml` — new path + 9 new component schemas, hand-spliced
  from a verified `app.openapi()` generation (not a full mechanical
  regeneration — the checked-in file has pre-existing formatting/description
  drift from a full auto-regen that predates this milestone and is out of
  scope to reconcile here; the new blocks were validated byte-for-byte
  against the live-generated schema before insertion).
- `tests/api/platform/test_dashboard_hosting.py`,
  `tests/api/platform/test_decision_chart_release_gate.py` — two
  pre-existing hardcoded-version assertions updated `9.204.0` → `9.205.0`
  (expected fallout of the mandatory asset-version-bump convention, not a
  behavior change).

**Files created (styling):**
- `src/athena/api/static/css/14-intraday-plan.css` — new, reuses only
  already-existing design tokens (verified each one exists in
  `00-tokens.css` before use).

**Source-review checklist (§20 of the implementation authorization), all
confirmed by direct inspection:**

| Check | Result |
|---|---|
| No duplicated sizing formula | Confirmed — `compose_position_sizing` calls `PositionSizingV0Engine.evaluate` unchanged; engine file untouched |
| No duplicated supervision methodology | Confirmed — `compose_live_plan_supervision` calls `LivePlanSupervisionEngine.evaluate` and reuses `compose_vwap_loss_evidence`/`compose_target_progress_evidence` from the engine module itself; engine file untouched |
| `PositionSizingV0Engine` unchanged | Confirmed — zero diff |
| `LivePlanSupervisionEngine` unchanged | Confirmed — zero diff |
| Exact EA currentness helper reused | Confirmed — `entry_actionability_currentness.is_currently_usable` called via module-qualified access (deliberately, to preserve an existing test's monkeypatch precedent — see below), never re-implemented |
| EQ coherence has no invented threshold | Confirmed — `resolve_entry_qualification_coherence` contains zero age/duration comparisons |
| ID-9 path performs no candle/provider read | Confirmed — `compose_position_sizing` takes no repository/candle parameter at all |
| ID-10 path is session-bounded | Confirmed — `session_day_start(market_checkpoint, session_tzinfo)` through `market_checkpoint`, identical shape to production |
| No API writes | Confirmed — `get_intraday_intelligence` calls zero `save_*` methods (source-scanned) |
| No hidden full validation execution | Confirmed — zero import of `DecisionEngine`/`ScoringEngine`/`ConfidenceEngine`/`RiskEngine`/`OwnerValidationPipeline` anywhere in the new service code |
| No cache | Confirmed — none added |
| No accidental 10s polling | Confirmed live in a real browser session: exactly one `GET .../intraday-intelligence` request per Decision Brief open, not present in the 10s quote-poll or dashboard-status poll cycles |
| No `total_deployable_capital` exposure | Confirmed by source (field absent from DTO) and by a live HTTP test asserting the string never appears in the response body |
| No SHORT methodology invention | Confirmed — SHORT still refused via the engines' own frozen `UNVALIDATED_DIRECTION` gate, verified live and in tests |
| No TradePlan mutation | Confirmed — zero diff to `domain/decision.py`/`decision/engine.py` |
| No EMR/DarvaX changes | Confirmed — zero diff to `explosive_move/`/`darvax/` |

**One implementation-time correction (source-review, not a design change):**
the original composition-module draft imported `is_currently_usable` as a
plain name (`from ... import is_currently_usable`), which broke one existing
test's monkeypatch (`test_id9_sizing_clock_instant_reused_for_currentness_and_evaluated_at`,
which patches the source module's own attribute expecting a fresh per-call
lookup). Fixed by importing the `entry_actionability_currentness` module
itself and calling `entry_actionability_currentness.is_currently_usable(...)`
— identical production behavior, restores monkeypatch-ability. No design
contract text changed; this is purely an implementation-technique fix
caught by the pre-existing test suite.

**Test results:**
- Focused new tests: 13 (`test_entry_qualification_coherence.py`) + 7
  (`test_intraday_composition.py`) + 7 (`test_decision_intraday_intelligence.py`)
  = 27 new tests, all passing.
- `tests/ops/test_owner_validation.py`: 92/92 passing, unchanged — proves
  the extraction is behavior-preserving.
- `tests/market_intel/` + `tests/ops/`: 825 passing (up from a
  pre-ID-11 baseline of 785 for that scope — +20 from the new coherence/composition
  test files, the HTTP integration tests live under `tests/api/`).
- `tests/api/` + `tests/market_intel/` + `tests/ops/`: 1248 passing.
- **Full repository suite (final, after all ID-11 work including the
  dashboard/CSS/OpenAPI changes): 4009 passed, 1 pre-existing unrelated
  skip, 0 failures.** This count already includes all 27 new ID-11 tests
  and the 2 corrected pre-existing hardcoded-dashboard-version assertions
  (`9.204.0`→`9.205.0`, an expected consequence of the mandatory
  asset-version-bump convention, not a behavior change) — the pre-ID-11
  full-suite baseline was 3982 passed/1 skipped.

**Live end-to-end verification:** an isolated, throwaway verification
server (separate port, separate temp SQLite DB, throwaway
`ATHENA_OWNER_PASSWORD_HASH` — the real production server on port 8000 was
never touched, restarted, or queried for credentials) was seeded with one
real `TRADE`+`QUALIFIED`+`ACTIONABLE` Decision/EntryQualification/EntryActionability
triple and exercised through a real browser:
- "Structural Plan Status" and "Structural Plan Freshness" labels render
  correctly (renamed from "Advisor status"/"Plan Status").
- The new "Intraday Plan" card renders: Qualification "Qualified", Entry
  "Actionable" with real Entry/Invalidation/T1/T2 values (₹100.00/₹98.00/₹101.00/₹101.50,
  matching the seeded data exactly).
- Because the real browser's wall clock was materially later than the
  seeded `evidence_as_of`, currentness correctly resolved to `STALE`, and
  Size/Live Status correctly rendered "Not sized"/"Not applicable" (the
  frozen `UPSTREAM_NOT_CURRENT` engine verdicts) — proving the §8 non-current
  semantics correction live, not just in tests.
- Network trace confirmed exactly one `GET .../intraday-intelligence` call
  for the brief-open event, with zero repeat calls during the subsequent
  10-second quote-poll ticks.
- Zero JavaScript console errors attributable to the new code (one
  unrelated pre-existing 404 from an isolated DarvaX satellite call for a
  symbol DarvaX has no data for).

**Remaining limitations / known debt (none blocking):**
- `docs/api/openapi.yaml`'s pre-existing top-level `info.description` and
  general formatting already differed from what a full mechanical
  regeneration would produce, predating this milestone — flagged, not
  fixed, since a full regen would produce a large unrelated diff (see the
  file-modified note above).
- The live end-to-end verification exercised the `STALE` non-current path
  live (naturally, via wall-clock drift) but not `SUPERSEDED`. This
  limitation was corrected by §22 below: `SUPERSEDED` is not structurally
  unreachable — it was an artifact of the original EA-resolution strategy
  (EA looked up by the exact current EQ identity, which can never disagree
  with itself), fixed by resolving EA by `decision_id` alone and letting
  `is_currently_usable` compare it against the current EQ identity.
  `SUPERSEDED` is now proven end-to-end through the real service/API in
  `tests/api/v1/test_decision_intraday_intelligence.py`, in addition to the
  composition-function level proof in `test_intraday_composition.py`.
- No dedicated OpenAPI-schema-coverage test or dashboard-JS unit test
  harness exists in this repository for this class of asset (none exists
  for any other Decision Brief section either) — coverage here is via the
  live HTTP integration tests plus the manual browser verification above.

---

## 22. Source-review correction (2026-09-09)

Owner/Chief Architect source review of §21's implementation found two
genuine source-level correctness defects, corrected in place, same
milestone (no ID-11.1/ID-11A/new milestone created). Nothing in §1-§20's
frozen design was reopened.

**1. EA repository selection made `SUPERSEDED` unreachable.**
`DecisionsService.get_intraday_intelligence` originally resolved
`EntryActionability` via
`latest_entry_actionability_for_entry_qualification(...)`, scoped to the
*current* EQ's own exact identity. Since that identity is by construction
the one just used to select the current EQ, an EA bound to an older EQ
observation for the same Decision could never be found by this lookup —
it always disagreed with itself, never with anything else — so
`is_currently_usable` was never given the chance to classify it
`SUPERSEDED`; the read model instead silently reported EntryActionability
`UNAVAILABLE`, even though a real, explainable historical EA existed.

Fixed by adding `SqliteRepository.latest_entry_actionability_for_decision
(decision_id)` (mirrors `latest_entry_qualification_for_decision`'s own
exact shape: decision-anchored, `ORDER BY entry_actionability_as_of DESC`,
no EQ-identity scoping) and switching the service to call it. EA selection
is now Decision-anchored only — never instrument-only, never an EQ-scoped
lookup — so an EA bound to an older EQ for the same Decision remains
reachable, and `is_currently_usable` (unchanged, called exactly as before)
is what classifies it `CURRENT`/`STALE`/`SUPERSEDED`/`SESSION_CLOSED`
against the *current* EQ identity. No new currentness logic, no schema
change, no change to `is_currently_usable` itself.

**2. Added an end-to-end `SUPERSEDED` proof.**
`tests/api/v1/test_decision_intraday_intelligence.py` gained
`TestIntradayIntelligenceSupersededSemantics::
test_superseded_ea_yields_real_engine_verdicts_never_unavailable`: persists
an EQ1 + an ACTIONABLE EA1 bound to EQ1, then persists a newer coherent
EQ2 for the same Decision, then asserts the live endpoint returns
`actionability.state == "ACTIONABLE"` (EA1's real persisted methodology
verdict, preserved for explainability) with
`actionability.currentness == "SUPERSEDED"`, and that
`sizing.state == "NOT_SIZED"`/`sizing.reason == "UPSTREAM_NOT_CURRENT"` and
`supervision.state == "NOT_APPLICABLE"`/
`supervision.reason == "UPSTREAM_NOT_CURRENT"` — the same frozen
non-current-EA engine verdicts already proven for `STALE`. `STALE`,
`SESSION_CLOSED` (unchanged), and the missing-EA `UNAVAILABLE` case all
remain distinct and independently tested.

**3. Removed the unauthorized public `?as_of=` parameter.**
The endpoint originally accepted a caller-supplied `as_of` query parameter
and threaded it into EQ coherence, EA currentness, PositionSizing,
LivePlanSupervision, the session candle cutoff, and `computed_at` — a
historical-replay capability never authorized for this Owner-facing
CURRENT-Intraday-Plan endpoint. Removed the `as_of` parameter from the
router and from `DecisionsService.get_intraday_intelligence`'s signature
entirely (no `replay=`/`checkpoint=`/`debug=` parameter introduced in its
place). `DecisionsService` gained an injectable `now_fn: Callable[[],
datetime] | None` constructor parameter (mirrors the existing
`MarketHistoryService`/`AdvisoryFreshnessService`/EMR-router `now_fn`/
`get_emr_request_clock` convention already used elsewhere in this API
layer), defaulting to the real wall clock; `api.dependencies
.get_decisions_service` reads an optional `request.app.state
.decisions_clock` to let tests inject a deterministic instant, exactly the
way the EMR router's `emr_clock` already does. Exactly one `self._now()`
read happens per `get_intraday_intelligence` call, reused for the EQ
`read_checkpoint`, EA currentness `now`, PositionSizing `now`/
`evaluated_at`, the on-demand LivePlanSupervision `market_checkpoint`/
`evaluated_at`, and the DTO's `as_of_summary.computed_at` — never two
independent clock reads in one response. Production `WorkflowStage` clock
semantics (`market_checkpoint = ctx.as_of`, `evaluated_at` = the
persistence/wall clock) are completely untouched — `compose_position_sizing`/
`compose_live_plan_supervision` still take both as explicit parameters and
were not modified.

`docs/api/openapi.yaml` corrected to match: the `as_of` query parameter
removed from the `/intraday-intelligence` path, and its `description` field
updated to state explicitly that this is a current, non-replay read —
verified via a live `app.openapi()` round-trip (`yaml.safe_load` equality
on the path's `parameters`/`description`).

**Files changed (this correction only):**
- `src/athena/data/store/repository.py` — new
  `latest_entry_actionability_for_decision(decision_id)`.
- `src/athena/api/v1/services/decisions_service.py` — EA lookup switched
  to the new decision-anchored method; `now_fn` constructor parameter
  added; `as_of` parameter removed from `get_intraday_intelligence`.
- `src/athena/api/dependencies.py` — `get_decisions_service` reads
  `request.app.state.decisions_clock` and passes it as `now_fn`.
- `src/athena/api/v1/routers/decisions.py` — `as_of` query parameter
  removed from the route.
- `tests/api/v1/test_decision_intraday_intelligence.py` — `_url()`'s
  `as_of` query-string mechanism replaced with a `_set_read_clock()`
  helper injecting `client.app.state.decisions_clock`; new
  `TestIntradayIntelligenceSupersededSemantics` test class (1 new test);
  `test_stale_ea_...`'s docstring corrected (no longer claims `SUPERSEDED`
  is unreachable).
- `docs/api/openapi.yaml` — `as_of` parameter and `description` corrected
  for this one path only.

**Validation:** `tests/api/v1/test_decision_intraday_intelligence.py` (8
tests, +1 from this correction), the full ID-6/7/9/10/11 regression set
(`tests/data_layer/test_entry_actionability_repository.py`,
`tests/data_layer/test_entry_qualification_repository.py`,
`tests/market_intel/test_intraday_composition.py`,
`tests/market_intel/test_entry_actionability_engine.py`,
`tests/market_intel/test_entry_actionability_models.py`,
`tests/market_intel/test_entry_actionability_currentness.py`,
`tests/market_intel/test_entry_qualification_coherence.py`,
`tests/ops/test_owner_validation.py`) all pass (369 passed). Full
repository suite and static/type checks reported in
`IMPLEMENTATION_SUMMARY.md`'s corresponding entry.

**Source-review confirmation (all 10 items proven directly against the
corrected source):**
1. `SUPERSEDED` is reachable through the real service/API — proven by the
   new end-to-end test above.
2. It is produced by `is_currently_usable(...)`, unchanged and called
   exactly as before — no new currentness branch was added anywhere in
   `decisions_service.py`/`intraday_composition.py`.
3. EA selection is Decision-anchored only
   (`latest_entry_actionability_for_decision(decision.decision_id)`) —
   confirmed by direct read of the corrected call site.
4. A genuinely missing EA (no row for this Decision at all) remains
   `UNAVAILABLE` — the `ea is None` branch is untouched.
5. `STALE` remains distinct — its existing test passes unchanged (with its
   docstring corrected).
6. `SESSION_CLOSED` remains distinct — untouched, `is_currently_usable`'s
   own frozen check order unchanged.
7. No public `as_of`/`checkpoint`/`replay` parameter remains on the route
   — confirmed by direct read of `decisions.py`'s route signature and by
   the live-`app.openapi()`-vs-`openapi.yaml` round-trip check.
8. Exactly one `self._now()` read is captured per call and reused for
   every downstream consumer — confirmed by direct read of
   `get_intraday_intelligence`'s body (single `now = self._now()` at the
   top, no other `datetime.now()` call anywhere in the method).
9. Production `WorkflowStage` clock semantics (`ctx.as_of`/persistence
   clock) are unchanged — `owner_validation.py`'s `position_sizing_stage`/
   `live_plan_supervision_stage` bodies were not touched by this
   correction.
10. No new writes, schema change, or methodology change occurred — `git
    diff` for this correction touches only the five files listed above
    (repository read method, service, dependencies, router, tests) plus
    this document and `IMPLEMENTATION_SUMMARY.md`.

**Final implementation classification:**

`ID11_IMPLEMENTATION_REVIEW_READY — 2026-09-09 — NOT YET OWNER APPROVED / CLOSED / FROZEN`
