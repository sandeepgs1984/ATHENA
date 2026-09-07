# ID-9 — Position Sizing V0 Core Implementation

Status: **ID-9 CAPITAL POLICY CONFIG HARDENED — READY FOR OWNER VALUES
/ FINAL ACTIVATION.** The Owner froze the ID-9 V0 core methodology/
implementation itself (classification
`ID9_V0_CORE_IMPLEMENTATION_METHODOLOGY_CORRECT_NO_PRODUCTION_ACTIVATION`,
§0/§34/§35 below — **nothing in §0-§35 changed by this round**). This
round (§36-§49, incl. §41a final config hardening) closes the one
remaining operational gap: a canonical production configuration seam
for `CapitalPolicy` now exists, wired into the same
`OwnerValidationPipeline` construction path production
already uses; production capital policy remains intentionally absent
until the Owner supplies four numeric values (§49).

## 0. Correction round (2026-09-07) — summary

Owner/Chief Architect source review accepted the V0 core sizing
mathematics and overall architecture in substance, and held final
closure for three correctness issues, all fixed in this same
implementation (no ID-9.1/ID-9.x created):

1. **Live sizing now enforces `EntryActionability` currentness.** A
   persisted `state == ACTIONABLE` is a methodology verdict at
   evaluation time, never a live-currentness guarantee — same-cycle
   synchronous production does not waive the frozen ID-7 evidence-age/
   session-phase contract. `PositionSizingV0Engine.evaluate` now
   requires a caller-supplied `CurrentnessResult` (from the existing,
   unmodified `entry_actionability_currentness.is_currently_usable`,
   never re-implemented) and refuses to size — `NOT_SIZED`/
   `UPSTREAM_NOT_CURRENT` — for anything other than `CURRENT`. See §9/§20.
2. **`policy_version` now participates in the artifact's own composite
   identity** (`PositionSizing.identity_tuple()`), and its presence
   rule was made precise: populated whenever a real `CapitalPolicy`
   genuinely participated in reaching a verdict (`SIZED`/
   `ZERO_QUANTITY_UNDER_POLICY`, and the narrow `NOT_SIZED`/
   `INVALID_RISK_GEOMETRY` case reached only after policy availability
   was confirmed), `None` otherwise. See §5/§18/§19.
3. **The silent `lot_size=1` fallback is removed.** `position_sizing_stage`
   now raises a contract error if canonical `Instrument` metadata is
   genuinely absent for an instrument reaching this stage (proven
   architecturally impossible, mirrors every instrument's own presence
   in the same `instruments` sequence this scan already resolved) — no
   fabricated lot size is ever used. See §14.

`position_sizing_as_of` semantics (§19) were reviewed and left
unchanged — genuinely the correct market-time checkpoint for V0 (no
change made merely for novelty). One wall-clock instant now serves both
the currentness `now` and this artifact's `evaluated_at` (§22, workflow
clock coherence). 19 new tests (16 pure-engine + 3 workflow); full suite
**3831 passed, 1 pre-existing unrelated skip, 0 failures** (up from
3812). Zero schema change (schema stays 18); zero new persistence; the
dormant P5.2-P5.6 pipeline remains `RETAIN_AS_LEGACY_COMPATIBILITY`,
untouched. Full detail in §35.

## 1. Executive verdict

A new, pure, deterministic V0 position-sizing engine
(`PositionSizingV0Engine`) and its immutable domain contract
(`PositionSizing`, `CapitalPolicy`) are implemented under
`src/athena/intraday/` — the same package `EntryQualification`/
`EntryActionability` live in — consuming `EntryActionability` directly
per the frozen Owner discovery decision (§2), and gated on the exact
same artifact's own read-time currentness (§0/§20) before ever sizing
it. LONG-only, three independent capital constraints (risk-budget,
max-position-value, theoretical-deployable-capital), quantity always
floored to whole lots, never forced to a minimum, zero score/RR/
confidence-weighted scaling of any kind. A new `position_sizing`
`WorkflowStage` wires it into the canonical per-instrument DAG,
`depends_on=("entry_actionability",)`, consuming the exact same-cycle
artifact — no persistence yet (`PERSISTENCE_NOT_YET_REQUIRED`, §21), no
capital policy read from dormant config (`self._capital_policy` defaults
to `None`, meaning every real cycle today honestly reports
`CAPITAL_POLICY_UNAVAILABLE` until the Owner explicitly wires one). The
dormant P5.2/P5.3 pipeline is left completely untouched and is not
imported by any ID-9 file (§3). 61 tests total (42 from the initial
implementation + 19 from this correction round); full suite **3831
passed, 1 pre-existing unrelated skip, 0 failures**. Zero schema/
production changes; `db/athena.db` confirmed unchanged (schema 18,
integrity ok); PID 2453 untouched; zero order/broker/execution
activation; zero EMR/DarvaX touch.

## 2. Owner-frozen discovery decisions (restated, unchanged)

Production upstream artifact: `EntryActionability` directly, no new
`EntryRisk` artifact. V0 direction scope: LONG only
(`LONG_VALIDATED_SHORT_UNVALIDATED` preserved). Capital mode:
`THEORETICAL_POLICY_CAPITAL_SIZING` (no live broker cash/margin; V0
never subtracts `owner_positions`/My Portfolio/broker positions). V0
must not depend on `owner_positions`, Portfolio Sync, broker balance,
live margin, sector-exposure ledger, or aggregate portfolio exposure —
confirmed: `grep` of the new modules for any of those terms returns
zero hits (§23 tests). Primary V0 constraints: risk-budget, max-
position-value, theoretical-deployable-capital quantities. Explicitly
deferred: liquidity, sector/instrument concentration, aggregate open
risk, same-direction exposure, daily loss budget, live available cash,
spread/depth/impact cost. `GOAL_BANDS_ONLY`/`RR_INFORMATIONAL_ONLY`
preserved — no multiplier uses RR/score/confidence/conviction/RS/RVOL/
T1-T2 attractiveness/historical hit rate (proven by source scan, §24).
Existing `capital.json`/`risk.json` numeric values are NOT implicitly
Owner-approved V0 policy — `CapitalPolicy` is an explicit, caller-
supplied object only, defaulting to `None` in production.

## 3. Existing dormant pipeline disposition (required classification)

| Component | Classification | Why |
|---|---|---|
| `CapitalAllocationEngine` (`allocation/engine.py`) | **RETAIN_AS_LEGACY_COMPATIBILITY** | Real, tested, code-complete — but consumes the generic pre-ID-track `Decision` object and a `PortfolioSnapshot` fed by the separate legacy `owner_positions` ledger; never invoked from `cli.py`/`runtime/`/`ops/`. Adapting it would require replacing its entire input contract (`Decision`→`EntryActionability`) and output shape (a single `allocated_amount`, no multi-constraint/binding-constraint concept) — an incoherent API change to an otherwise-working, independently-tested class. Left untouched; not imported by any ID-9 file. |
| `PositionSizingEngine` (`sizing/engine.py`) | **RETAIN_AS_LEGACY_COMPATIBILITY** | Same reasoning: its `size_plan()`/`size_amount()` convert one already-decided rupee `allocated_amount` into a share count — a fundamentally different paradigm from ID-9's risk-budget/max-value/theoretical-capital minimum-of-three-constraints model. Its own `PositionSize`/`PositionSizingPlan` domain objects have no field for `per_share_risk`, multiple candidate quantities, or a `binding_constraint`. Rewriting it into ID-9's shape would break its own existing tests/callers for zero benefit, since nothing in production calls it today anyway. Left untouched. |
| `OrderPlanningEngine`, `BrokerManager`, `OrderLifecycleEngine` | **RETAIN_AS_LEGACY_COMPATIBILITY** | Downstream of the above two, same disposition; ID-9 ends at advisory `PositionSizing`, never reaching order/broker/execution concerns at all (§18). |
| `AllocationPlan`, `CapitalAllocation` (`allocation/models.py`) | **RETAIN_AS_LEGACY_COMPATIBILITY** | Domain objects for the dormant allocation engine; not reused, not referenced by any ID-9 code. |
| `PositionSizingPlan`, `PositionSize` (`sizing/models.py`) | **RETAIN_AS_LEGACY_COMPATIBILITY** | Same — the `RoundingMode`/`SizingModel` *enums* they depend on (`config/models.py`) are generic, reusable vocabulary (ROUND_DOWN/WHOLE_SHARE mean the same thing everywhere), but ID-9 defines its own small `_floor_to_lot`/`_floor_money` helpers rather than importing `sizing/engine.py`'s private `_calculate_quantity` (a private method, not a public API, and lacking lot-size-multiple flooring — it only floors to whole integers). |
| `AllocationConfig`, `SizingConfig` (`config/models.py`) | **RETAIN_AS_LEGACY_COMPATIBILITY** | Real, loaded, consumed only by the dormant engines above. `CapitalPolicy` (ID-9's own new, minimal contract) deliberately does NOT subclass or wrap these — see §6 for why. |
| `CapitalConfig`, `RiskConfig` (`config/capital.json`/`config/risk.json`) | **RETAIN_AS_LEGACY_COMPATIBILITY** | Loaded by the config system, consumed by zero engines (confirmed in the ID-9 discovery report). Left untouched; not read by ID-9 (§6 explains the explicit-policy-only design instead). |

**No ambiguous outcome**: production has exactly ONE canonical sizing
path after this milestone — `PositionSizingV0Engine`
(`athena.intraday.position_sizing_engine`), wired into the one live
per-instrument `WorkflowStage` DAG. The dormant P5.2-P5.6 pipeline
remains present (for whatever future purpose the Owner may still have
for it), completely inert in production (confirmed unreachable from
`cli.py`/`runtime/`/`ops/` both before and after this milestone — proven
by source-scan test, §23), and never imported by any new ID-9 file
(proven by source-scan test, §23).

## 4. Canonical sizing architecture

`src/athena/intraday/position_sizing_models.py` (domain contracts +
`CapitalPolicy`) and `src/athena/intraday/position_sizing_engine.py`
(the pure `PositionSizingV0Engine.evaluate(...)` evaluator) — placed
directly alongside `entry_actionability_models.py`/
`entry_actionability_engine.py`, following that exact established
naming/layering convention (ID-9 is ADR-013's next downstream layer).
The engine class is named `PositionSizingV0Engine`, deliberately
differentiated from the dormant `athena.sizing.engine.PositionSizingEngine`
— different module, different package, no shared base class, no runtime
coupling in either direction (§3/§23).

## 5. Domain model

`PositionSizing` (frozen dataclass, `intraday/position_sizing_models.py`):
**composite identity (corrected, §0 item 2)** = the entire upstream
`EntryActionability` composite key copied verbatim (`instrument_id`,
`session_date`, `entry_qualification_as_of`, `decision_id`,
`entry_qualification_methodology_version`, `entry_actionability_as_of`),
plus this artifact's own `position_sizing_as_of`/
`sizing_methodology_version`, **plus `policy_version`** — no surrogate
id, mirroring `EntryActionability`'s own frozen identity model but
extended one field further, exposed explicitly via a new
`identity_tuple()` method (mirrors
`entry_actionability_currentness.bound_entry_qualification_identity`'s
own "derived view over already-stored fields" pattern). Two sizing
assertions over the exact same upstream checkpoint under two different
`CapitalPolicy` versions are genuinely different assertions (e.g.
policy-v1 → quantity 100 vs. policy-v2 → quantity 50) and must never
compare as the same identity — proven directly
(`test_identity_tuple_differs_across_policy_versions_for_same_entry_actionability`,
`test_domain_identity_tuple_includes_policy_version`), while
`sizing_methodology_version` itself remains provably unchanged across
policy versions (`test_sizing_methodology_version_unchanged_across_policy_versions`)
— POLICY VERSION and SIZING METHODOLOGY VERSION remain independent
dimensions; only the *artifact's* identity is now the combination of
both.

Three independent field-presence rules (never conflated, refined from
two in §0 item 2): (1) upstream-echoed risk-geometry fields (`direction`,
`entry_reference_price`, `operative_invalidation_level`, `per_share_risk`)
present whenever `UPSTREAM_NOT_ACTIONABLE` is not in `reason_codes`
(now also true for the new `UPSTREAM_NOT_CURRENT` case, §20); (2)
`policy_version` present whenever a real `CapitalPolicy` genuinely
participated — always for `SIZED`/`ZERO_QUANTITY_UNDER_POLICY`, and
additionally for the narrow `NOT_SIZED`/`INVALID_RISK_GEOMETRY` case
(reached only after policy availability was already confirmed), never
for `UPSTREAM_NOT_ACTIONABLE`/`UNVALIDATED_DIRECTION`/
`UPSTREAM_NOT_CURRENT`/`CAPITAL_POLICY_UNAVAILABLE` (policy never
inspected) — see the new `POLICY_PARTICIPATED_NOT_SIZED_REASON_CODES`
frozenset; (3) the other capital-derived and result fields present iff
`state in (SIZED, ZERO_QUANTITY_UNDER_POLICY)`. `__post_init__` enforces
all three rules plus the derived-value invariants of §17, mirroring
`EntryActionability.__post_init__`'s own "reject an untruthful supplied
combination" philosophy (19 dedicated domain-construction tests total
across both rounds, §26).

## 6. Policy model/adapter

`CapitalPolicy` (frozen dataclass): `total_deployable_capital: Decimal`,
`risk_budget_per_trade_pct: Decimal`, `max_position_value_pct: Decimal`,
`policy_version: str`. **Deliberately NOT** `CapitalConfig`/`RiskConfig`
themselves (pydantic config-loader classes) — reusing them directly
would (a) carry V0-irrelevant fields into a "keep V0 minimal" contract
(`max_capital_per_sector_pct`, `max_daily_loss_pct`, `max_consecutive_losses`,
...), and (b) implicitly couple the engine's own explicit-policy-input
contract to file-based config loading conventions the Owner's own
instruction explicitly warned against silently defaulting to. `CapitalPolicy`
reuses `CapitalConfig`/`RiskConfig`'s own field *semantics* and *percent-number
convention* (e.g. `Decimal("0.5")` meaning 0.5%, never a 0-1 fraction) —
a thin, minimal, explicit "view," not a duplicate configuration
universe. `policy_version` is independent of `sizing_methodology_version`
(`DEFAULT_METHODOLOGY_VERSION = "position-sizing-v0"`) — a policy-value
change can never masquerade as a methodology-version change (§19).

## 7. Policy-value handling

`OwnerValidationPipeline.__init__` gained one new optional, injectable
parameter: `capital_policy: CapitalPolicy | None = None`, stored as
`self._capital_policy`, mirroring the exact existing `persistence_clock`
injectable-optional pattern. **Production default is `None`** — no
`capital.json`/`risk.json` value is read anywhere in the new code
(confirmed by source-scan test, §23). Every real cycle today, until the
Owner explicitly constructs and passes a real `CapitalPolicy`, honestly
reports `CAPITAL_POLICY_UNAVAILABLE` for every opportunity — proven
end-to-end against the real workflow (§23,
`test_id9_no_capital_policy_configured_by_default_reports_unavailable`).

## 8. `EntryActionability` binding

`position_sizing_stage` reads `ctx.get("entry_actionability")` — the
exact same-cycle object `entry_actionability_stage` itself just
produced — never a repository "latest" re-query (proven by source-scan
test, §23:
`test_id9_no_latest_repository_query_for_same_cycle_sizing`, and
end-to-end by `test_id9_capital_policy_injected_produces_sized_result`'s
identity comparison against the persisted row). Gated on
`entry_actionability is None` (the out-of-scope-Decision-type case,
ADR-015/ID-7E.1's own funnel) BEFORE any instrument/policy composition
— proven by a direct call-count spy showing zero `evaluate()` invocations
for a genuine `NO_TRADE` Decision (§23). A WATCH-bound (non-`None`,
`NOT_ACTIONABLE`) `EntryActionability` correctly still reaches
`evaluate()`, which itself gates on `state != ACTIONABLE` first, inside
the pure engine (§9) — proven end-to-end (§23,
`test_id9_watch_decision_reaches_upstream_not_actionable`).

## 9. LONG-only gate

`PositionSizingV0Engine.evaluate` checks `entry_actionability.state is
ACTIONABLE` first (§8's upstream gate, mirroring
`EntryActionabilityEngine`'s own gates-first evaluation order, ID-7C.2's
corrected precedent). Then, for a genuinely-`ACTIONABLE` artifact, a
defensive assertion (`direction in (LONG, SHORT)`) raises `ValueError`
for the structurally-impossible `NONE` case (mirroring
`EntryActionabilityEngine._validate_binding`'s own "reject an
impossible supplied combination" philosophy — never gracefully reported
as a `PositionSizing` result, since `PositionSizing`'s own domain
invariant would reject constructing one for a non-LONG/SHORT direction
anyway). SHORT is then refused with `UNVALIDATED_DIRECTION`, still
echoing its own real, correctly-signed per-share risk for
explainability (geometry validity and direction-validation scope are
independent concepts, per instruction). **The full, corrected gate
order (§0 item 1) is: upstream-`ACTIONABLE` → direction (LONG-only) →
currentness (§20) → capital-policy availability → defensive risk-
geometry → sizing math** — matching the Owner's own explicit
evaluation-order example list exactly: currentness is never bypassed by
policy, and policy is never inspected for a non-current opportunity. 4
dedicated direction tests (§26).

## 10. Per-share risk

`per_share_risk = entry_reference.price - operative_invalidation.level`
for LONG — no `abs()`. Defensively re-checked `> 0` even though
`EntryActionability`'s own `_validate_risk_geometry` invariant already
structurally guarantees this whenever `state == ACTIONABLE` and
`direction == LONG` — the defensive branch (`INVALID_RISK_GEOMETRY`) is
tested by deliberately bypassing that upstream invariant via a direct
`object.__setattr__` construction (the only way to reach a code path
that should be, and is documented as, unreachable through any legally-
constructed input). Decimal throughout — no binary float anywhere in
the module (confirmed by a dedicated type-check test, §23).

## 11. Risk-budget quantity

`risk_budget_amount = floor_money(total_deployable_capital ×
risk_budget_per_trade_pct / 100)`; `risk_quantity =
floor_to_lot(risk_budget_amount / per_share_risk, lot_size)`. Both
floors — `floor_money` (2-decimal-place `ROUND_DOWN`, never inflating a
budget ceiling) and `floor_to_lot` (whole-multiple-of-`lot_size` floor,
never rounding up, never forcing a minimum) — are dedicated, tested
pure functions in the new module, never binary float.

## 12. Max-value quantity

`max_position_value = floor_money(total_deployable_capital ×
max_position_value_pct / 100)`; `max_value_quantity =
floor_to_lot(max_position_value / entry_reference.price, lot_size)` —
computed completely independently of the risk-budget calculation, never
algebraically merged (verified directly: `risk_budget_per_trade_pct`
and `max_position_value_pct` are two entirely separate `CapitalPolicy`
fields, each used in exactly one place).

## 13. Theoretical-capital quantity

`theoretical_available_capital = total_deployable_capital` (V0 never
subtracts `owner_positions`/My Portfolio holdings/broker positions, per
the frozen `THEORETICAL_POLICY_CAPITAL_SIZING` mode);
`theoretical_capital_quantity = floor_to_lot(theoretical_available_capital
/ entry_reference.price, lot_size)`. **A genuine mathematical finding
from implementation** (documented in the engine's own test suite,
§23): since `max_position_value_pct ≤ 100%` is enforced by
`CapitalPolicy.__post_init__`, `max_position_value ≤
theoretical_available_capital` always holds, so
`theoretical_capital_quantity ≥ max_value_quantity` always — the
theoretical-capital constraint can therefore never be the UNIQUE
tightest constraint; it can only ever co-bind with `MAX_POSITION_VALUE`
at the `max_position_value_pct == 100%` boundary. This is reported
honestly, not hidden — a dedicated test
(`test_theoretical_capital_co_binds_with_max_value_at_full_deployment`)
proves the real relationship rather than asserting an impossible
"theoretical-capital-alone-binds" scenario.

## 14. Lot-size rounding

`instrument.lot_size` is read from the same `instruments` sequence
`_scan_eligible` already resolves for the whole run (no second
repository read) via a new `instrument_by_id` map. **Corrected (§0 item
3): the prior silent `else 1` fallback for a missing map entry is
removed.** Every instrument reaching `position_sizing_stage` was itself
sourced from that same `instruments` sequence (`UniverseEngine.build`'s
own input, traced directly — `included_ids` is built from
`universe_engine.build(instruments, ...)`'s own `result.assessments`,
so `instrument_by_id.get(instrument_id)` returning `None` here would be
a genuine invariant violation, never a plausible runtime condition).
`position_sizing_stage` now raises `ValueError` immediately if
`instrument` is `None`, and separately if `instrument.lot_size < 1`
(defensive, since `Instrument.__post_init__` already enforces this) —
proven by source-scan test
(`test_id9_no_silent_lot_size_fallback_in_stage`) that the old fallback
literal is gone and an explicit raise/`is None` guard exists. Never
hardcoded to `1` in the engine itself — `_floor_to_lot` takes `lot_size`
as a genuine parameter and is tested with a non-1 lot size
(`instrument_lot_size=7`) to prove the flooring logic is generic, not
merely "always divides by 1." `ROUND_DOWN`/floor only, everywhere —
never `ROUND_UP`, never a forced minimum of one lot. No tick-size price
rounding was introduced (per explicit instruction — ID-9 consumes
upstream reference prices, never creates executable limit/stop-order
prices).

## 15. Zero-quantity semantics

If `min(risk_quantity, max_value_quantity, theoretical_capital_quantity)
<= 0`: `state = ZERO_QUANTITY_UNDER_POLICY`, `recommended_quantity =
Decimal("0")`, never forced to one share/lot, never reported as `SIZED`
with a zero quantity (the domain model's own `__post_init__` rejects
that combination — proven by a dedicated negative test, §23). Every
candidate quantity and the binding-constraint set are still genuinely
populated (the computation ran; only its result was zero) — proven by a
dedicated test asserting `risk_quantity`/`max_value_quantity` are not
`None` even in the zero-quantity case.

## 16. Binding constraints

`BindingConstraint` enum (`RISK_BUDGET`, `MAX_POSITION_VALUE`,
`THEORETICAL_CAPITAL`). `binding_constraints: tuple[BindingConstraint, ...]`
reports every candidate whose quantity equals the achieved minimum —
never collapsed to one arbitrarily-chosen winner. A dedicated two-way
co-binding test (`test_two_way_co_binding_reports_both_constraints`)
proves an exact tie between `RISK_BUDGET` and `MAX_POSITION_VALUE` is
reported as both, in declaration order, never one.

## 17. Derived-value invariants

For `SIZED`/`ZERO_QUANTITY_UNDER_POLICY`: `capital_at_risk =
floor_money(recommended_quantity × per_share_risk)`,
`recommended_position_value = floor_money(recommended_quantity ×
entry_reference.price)`. The domain model's own `__post_init__`
enforces `capital_at_risk <= risk_budget_amount`,
`recommended_position_value <= max_position_value`, and
`recommended_position_value <= theoretical_available_capital` as hard
invariants (raising `ValueError` if violated) — proven both positively
(`test_derived_value_invariants_hold_for_sized_result`, real computed
values) and negatively (`test_domain_rejects_capital_at_risk_exceeding_budget`,
a deliberately-violating synthetic construction). These hold by
construction given the flooring in §11-13, since floor-quantizing a
monetary amount can only ever decrease it.

## 18. State/reason semantics

Three states only (`SIZED`/`NOT_SIZED`/`ZERO_QUANTITY_UNDER_POLICY`) —
no `UNKNOWN` member was needed; every V0 failure mode maps truthfully to
one of the three. Reason-code families mirror
`EntryActionabilityReasonCode`'s own separation exactly:
`NOT_SIZED_REASON_CODES = {UPSTREAM_NOT_ACTIONABLE, UNVALIDATED_DIRECTION,
UPSTREAM_NOT_CURRENT, CAPITAL_POLICY_UNAVAILABLE, INVALID_RISK_GEOMETRY}`
(**`UPSTREAM_NOT_CURRENT` added this correction round, §0 item 1**),
`ZERO_QUANTITY_REASON_CODES = {ZERO_QUANTITY_UNDER_POLICY}`, and a new
`POLICY_PARTICIPATED_NOT_SIZED_REASON_CODES = {INVALID_RISK_GEOMETRY}`
(§0 item 2 — the only `NOT_SIZED` reason whose verdict still carries a
`policy_version`). `SIZED` requires empty `reason_codes` (mirroring
`ACTIONABLE`'s own "not blocked" invariant). Every mapping from the
Owner's own instructions (upstream not ACTIONABLE → NOT_SIZED;
SHORT/NONE → NOT_SIZED + UNVALIDATED_DIRECTION; non-current →
NOT_SIZED + UPSTREAM_NOT_CURRENT; policy missing → NOT_SIZED +
CAPITAL_POLICY_UNAVAILABLE; invalid geometry → NOT_SIZED +
INVALID_RISK_GEOMETRY; quantity floors below lot →
ZERO_QUANTITY_UNDER_POLICY; valid positive quantity → SIZED) is
implemented exactly and independently tested.

## 19. Provenance/timestamps

`entry_qualification_as_of`, `decision_id`,
`entry_qualification_methodology_version`, `entry_actionability_as_of`,
`entry_actionability_methodology_version` copied verbatim from the bound
`EntryActionability` — proven by a dedicated exact-provenance test
(§23). `evidence_as_of` echoed independently (present or `None`
depending on the upstream artifact's own value, never re-derived).
`position_sizing_as_of` is set equal to `entry_actionability_as_of`
(Option-1-style synchronous evaluation, mirroring
`entry_actionability_as_of = entry_qualification.as_of`'s own ID-7C
precedent) — V0 deliberately does not exercise any future same-EQ
re-evaluation capability. **Reviewed per §0's own explicit instruction
and left unchanged**: ID-9 V0 is a deterministic capital projection over
the exact same market-time checkpoint `EntryActionability` itself
asserts — sizing introduces no distinct market-time assertion of its
own (it answers "how much," not "when," a question already settled by
the bound `EntryActionability`), so reusing `entry_actionability_as_of`
is the correct, not merely convenient, choice; changing it would imply
a market-time claim this artifact does not make. `sizing_methodology_version =
DEFAULT_METHODOLOGY_VERSION = "position-sizing-v0"`, minted and frozen
here, independent of `policy_version` (§6/§18's own explicit separation,
now also reflected in `identity_tuple()`, §5). `evaluated_at` is the
one captured wall-clock instant (`sizing_clock_instant`, §22) — **now
explicitly proven (§0 item "clock coherence") to be the SAME instant
passed as `now` to the currentness check**, never two independent clock
reads for one sizing decision, and never `entry_actionability_stage`'s
own separate clock call or `ctx.as_of` — proven end-to-end by
`test_id9_sizing_clock_instant_reused_for_currentness_and_evaluated_at`
(spies on `is_currently_usable`'s own `now` kwarg and asserts exact
equality with the injected `persistence_clock` instant).

## 20. Currentness

**Corrected, §0 item 1 — this section's own prior claim was wrong and
is withdrawn.** The initial implementation argued that same-cycle
synchronous evaluation made currentness unnecessary for V0; the Owner's
source review correctly rejected this: `EntryActionability.state ==
ACTIONABLE` is a persisted, evaluation-time-only methodology verdict
(ID-7A0.1's own frozen dimension A) — it says nothing about whether the
artifact is usable for a LIVE recommendation right now, and a real
canonical cycle can take long enough for a completed-M5 evidence
checkpoint to cross the frozen 10-minute currentness boundary before
`position_sizing_stage` itself runs.

**Fix — the existing ID-7 contract is reused directly, never
duplicated.** `PositionSizingV0Engine.evaluate` now takes a mandatory
`currentness: CurrentnessResult` parameter (from
`entry_actionability_currentness`) and gates on
`currentness.status is EntryActionabilityCurrentness.CURRENT` (§9's
corrected gate order) — any other status (`STALE`, `SUPERSEDED`,
`SESSION_CLOSED`, or even `METHODOLOGY_NOT_ACTIONABLE`) yields
`NOT_SIZED`/`UPSTREAM_NOT_CURRENT`. The engine itself computes nothing —
no clock, repository, provider, or session-service read of any kind
(confirmed by source-scan test, §26) — it only inspects an
already-derived value.

**Composition happens in the workflow, not the pure engine** (§22):
`position_sizing_stage` captures one wall-clock instant
(`sizing_clock_instant = self._persistence_clock()`) and calls the
real, unmodified `is_currently_usable(entry_actionability,
current_decision_id=decision.decision_id,
current_entry_qualification_identity=EntryQualificationIdentity(...from
ctx.get("entry_qualification")...), current_session_phase=classify_session_phase(...),
now=sizing_clock_instant)`. `current_session_phase` is resolved via the
existing, cheap, candle-free `session.classify_session_phase(...)`
helper (`calendar.context_for(...)` + `cfg.market.sessions`) evaluated
at the REAL `sizing_clock_instant`, not the cycle's nominal `ctx.as_of`
— this is precisely the dimension that can genuinely differ from the
identity checks (which trivially always agree in a same-cycle
synchronous design, since `entry_actionability`'s own bound EQ identity
was copied verbatim from the very same `entry_qualification` object
this stage also reads).

**Non-current results preserve historical truth**: the persisted
`EntryActionability` row is never mutated, never relabeled
`NOT_ACTIONABLE`, and `STALE`/`SUPERSEDED`/`SESSION_CLOSED` are never
written into it — only the new, purely-in-memory `PositionSizing`
result reports `UPSTREAM_NOT_CURRENT`, exactly mirroring dimension A/
dimension B's own architectural independence (ID-7A0.1).

Tests (§26): `CURRENT` proceeds to sizing; `STALE`/`SUPERSEDED`/
`SESSION_CLOSED` each independently refuse with `UPSTREAM_NOT_CURRENT`;
the gate is proven to precede capital-policy availability (a non-current
+ no-policy combination still reports `UPSTREAM_NOT_CURRENT`, never
`CAPITAL_POLICY_UNAVAILABLE`); a full real-pipeline test forces the
sizing-stage clock 11 minutes past a real `evidence_as_of` and proves
the real `SIZED`-shaped fixture correctly refuses instead
(`test_id9_stale_evidence_does_not_size`); and the WATCH-Decision
pipeline test (§8) independently proves `UPSTREAM_NOT_ACTIONABLE` is
still checked (and wins) before currentness is ever consulted at all,
for an artifact that was never `ACTIONABLE` in the first place.

## 21. Persistence decision

**`PERSISTENCE_NOT_YET_REQUIRED`.** The pure evaluator is fully
implemented and tested standalone (34 tests exercise it directly with
zero repository/workflow involvement); the workflow stage publishes its
result into `WorkflowContext` only (`{"position_sizing": sizing}`), for
this cycle's own in-memory consumers — no `save_position_sizing`
repository method exists, no schema change, `schema_version` remains
18. This mirrors `EntryActionabilityEngine`'s own ID-7C precedent
(shipped pure before persistence, which came later via ID-7A/ID-7E).
No concrete production/audit/API requirement for historical
`PositionSizing` reads was identified during this milestone — inventing
persistence now, with `self._capital_policy` still defaulting to `None`
in production (so every real observation today would be an unvarying
`CAPITAL_POLICY_UNAVAILABLE` row), would add schema/repository surface
area with no genuine consumer yet.

## 22. Workflow integration

New `position_sizing` `WorkflowStage`, `depends_on=("entry_actionability",)`,
`produces=("position_sizing",)`, declared last in the DAG (nothing
depends on it, so it cannot perturb the twelve pre-existing stages'
relative order — proven by a dedicated order-preservation test mirroring
ID-7E's own). A dedicated transitive-dependency test proves (via
`WorkflowEngine`'s own generic failure/skip propagation, not insertion
order) that `entry_actionability`'s own completion already guarantees
every one of its ancestors completed. The stage gates on
`entry_actionability is None` before any instrument/policy composition
(§8) — an out-of-scope Decision can never even reach engine invocation.

**Corrected, §0: currentness composition and clock coherence.** The
stage now also resolves `instrument`/`lot_size` (§14, contract-error on
absence, no fallback), captures exactly one `sizing_clock_instant`, and
composes the `CurrentnessResult` via the real `is_currently_usable`
before calling the engine — all inside the same stage body, in this
order: entry_actionability-is-None gate → instrument/lot-size
resolution → single clock capture → currentness composition → engine
call (passing `currentness=`, `capital_policy=self._capital_policy`,
`instrument_lot_size=lot_size`, `evaluated_at=sizing_clock_instant`).
No second `self._persistence_clock()` call exists anywhere in the
stage — proven by
`test_id9_sizing_clock_instant_reused_for_currentness_and_evaluated_at`.

## 23. Legacy-path isolation

Proven by dedicated source-scan tests:
`test_engine_never_imports_dormant_legacy_sizing_pipeline` (neither
`position_sizing_models.py` nor `position_sizing_engine.py` imports
anything from `athena.allocation`/`athena.sizing`/`athena.orders`/
`athena.brokers`/`athena.execution`); `test_engine_never_calls_provider_network_or_persistence`
(no `kite`/`requests.`/`httpx.`/`urllib.request`/`self._repo`/
`save_position_sizing`/`insert into` anywhere in either module);
`test_id9_no_persistence_no_provider_calls_in_stage` and
`test_id9_no_latest_repository_query_for_same_cycle_sizing` (the same
proofs at the workflow-stage level). Combined with §3's confirmation
that the dormant pipeline is (and remains) unreachable from `cli.py`/
`runtime/`/`ops/`, production has exactly one canonical sizing path.

## 24. No-liquidity/concentration proof

`test_engine_source_never_references_score_confidence_conviction_rs_rvol`
scans the engine's own code (module docstring excluded) for `score`,
`confidence`, `conviction`, `rs_pct`, `rvol`, `hit_rate`, `kelly` — none
present. `test_engine_source_never_reads_reward_t1_t2_rr` (code only,
docstring excluded) proves `EntryActionability.reward`/
`reward_risk_to_t1`/`reward_risk_to_t2`/`t1_price`/`t2_price` are never
read. `test_extreme_rr_does_not_change_sizing_result` proves this
behaviorally: an identical opportunity with an artificially extreme RR
produces the exact same `recommended_quantity`/`binding_constraints`.
No liquidity/concentration field or gate exists anywhere in
`PositionSizing`/`CapitalPolicy` at all — not merely unused, structurally
absent from the contract.

## 25. No-order/execution proof

`OrderPlanningEngine`/`BrokerManager`/`OrderLifecycleEngine` are never
imported, referenced, or instantiated anywhere in the new ID-9 code
(§23's import-scan test covers this directly). `position_sizing_stage`
produces `PositionSizing` only and stops there — `produces=("position_sizing",)`
is the DAG's own terminal declaration for this milestone; no
`order_planning`/`broker_translation`/`execution` stage was added.

## 26. Test matrix

**61 tests total (42 from the initial implementation + 19 from this
correction round).** `tests/market_intel/test_position_sizing_engine.py`
(50, +16 this round): valid LONG sizing, risk-budget binding, max-
position-value binding, theoretical-capital co-binding (§13's own
mathematical finding), two-way co-binding, lot-size floor (non-1 lot),
zero-quantity-never-forced, derived-value invariants, SHORT refused,
NONE refused (contract error, §9), missing-policy refused, upstream-
not-actionable refused (without reading geometry), invalid-geometry
refused (defensive, now also proven to preserve `policy_version`),
naive-`evaluated_at`/sub-1-lot-size rejection, Decimal-only-arithmetic,
exact-provenance, policy-version-echo, deterministic repeat, RR/T1/T2-
never-read (source scan + behavioral), no-provider/persistence/legacy-
pipeline-import (source scans), 19 domain-model construction/rejection
tests, 3 `CapitalPolicy` validation tests, **plus this round's new
currentness tests** (CURRENT proceeds; `STALE`/`SUPERSEDED`/
`SESSION_CLOSED`/`METHODOLOGY_NOT_ACTIONABLE` each independently refuse
with `UPSTREAM_NOT_CURRENT`; currentness gate proven to precede
capital-policy availability) **and policy-identity tests**
(`identity_tuple()` differs across policy versions for the identical
upstream checkpoint; `sizing_methodology_version` proven unchanged
across policy versions; different policy versions proven able to change
`recommended_quantity`; `policy_version is None` proven for
`UPSTREAM_NOT_CURRENT`/`UPSTREAM_NOT_ACTIONABLE`/`UNVALIDATED_DIRECTION`;
domain-level rejection of an illegally-populated `policy_version` for a
non-participated `NOT_SIZED` reason; domain-level requirement of
`policy_version` for `INVALID_RISK_GEOMETRY`).

`tests/ops/test_owner_validation.py` (11, +3 this round): DAG order
preservation, transitive dependency, out-of-scope-Decision non-
invocation (call-count spy), WATCH-reaches-`UPSTREAM_NOT_ACTIONABLE`,
no-policy-by-default (`CAPITAL_POLICY_UNAVAILABLE` end-to-end),
policy-injected produces `SIZED` with exact same-cycle
`EntryActionability` identity proof, no-persistence/no-provider source
scan, no-latest-repository-query source scan, **plus this round's**
real-pipeline stale-evidence-refuses-sizing proof
(`test_id9_stale_evidence_does_not_size`), sizing-clock-instant-reused
proof (`test_id9_sizing_clock_instant_reused_for_currentness_and_evaluated_at`,
spies on `is_currently_usable`'s own `now` kwarg), and the no-silent-
lot-size-fallback source-scan proof
(`test_id9_no_silent_lot_size_fallback_in_stage`). Two pre-existing
tests were touched this round (both `test_id7e1_no_dag_change`'s own
locked-in literal-count assertion, updated 4→9 with an explanation, and
`test_id7e_no_currentness_no_provider_no_config_in_stage`, re-scoped to
`entry_actionability_stage`'s own body only, since ID-9's own
`position_sizing_stage` — a different, later stage — now legitimately
reuses currentness concepts for its own live-currentness gate) — no
other pre-existing test was touched, and neither change weakens the
original ID-7E invariant each was written to prove.

## 27. Full suite

**3831 passed, 1 pre-existing unrelated skip, 0 failures** (up from
3812 before this correction round, exactly +19; up from 3770 before the
original ID-9 implementation, exactly +61 total).

## 28. Production safety

Zero provider/network calls (confirmed by source scan, §23/§25). Zero
order/broker calls. `schema_version` confirmed unchanged at 18 both
before and after this milestone's full test run;
`PRAGMA integrity_check` returns `ok`. PID 2453 (`athena.cli serve
--with-cycles`) confirmed running, unchanged, throughout (continuous
uptime spanning this and every prior milestone in this session). No
production restart performed or required (this milestone made no
schema/repository change).

## 29. EMR isolation

Not referenced, not touched. `explosive_move/` package untouched.

## 30. DarvaX isolation

Not touched. `darvax/positions/models.py`'s own `DarvaxPosition` was
inspected only during discovery (prior milestone) and confirmed not a
sizing precedent; no DarvaX file was read or modified this milestone.

## 31. Files changed

**This correction round** modified (no new source/test files created):
`src/athena/intraday/position_sizing_models.py` (`UPSTREAM_NOT_CURRENT`
reason code, `POLICY_PARTICIPATED_NOT_SIZED_REASON_CODES`, refined
`policy_version` presence invariant, `identity_tuple()`), `src/athena/intraday/position_sizing_engine.py`
(mandatory `currentness` parameter, currentness gate, `policy_version`
preserved for `INVALID_RISK_GEOMETRY`), `tests/market_intel/test_position_sizing_engine.py`
(16 new tests + `currentness=_CURRENT` added to every pre-existing
engine call), `src/athena/ops/owner_validation.py` (currentness
composition in `position_sizing_stage`, lot-size fallback removed,
`classify_session_phase`/`is_currently_usable`/`EntryQualificationIdentity`
imports added), `tests/ops/test_owner_validation.py` (3 new tests + 2
pre-existing tests updated per §26), this report (`docs/research/ID-9-POSITION-SIZING-V0-CORE-IMPLEMENTATION.md`).
Tracking-doc updates for THIS correction round (`docs/MILESTONES.md`,
`ATHENA_BRIEFING.md`, `IMPLEMENTATION_SUMMARY.md`,
`docs/ATHENA-ID-TRACK-HANDOFF.md`) are listed in this same commit's own
accounting, per the mandatory milestone-tracking workflow. Zero schema/
repository/config file touched; zero new persistence.

Original implementation (unchanged from the prior round, preserved for
record): `src/athena/intraday/position_sizing_models.py`/
`position_sizing_engine.py` created, `src/athena/intraday/__init__.py`
(new exports), `src/athena/ops/owner_validation.py` (new
`capital_policy` constructor parameter, `instrument_by_id` lookup map,
`position_sizing_stage`, new `WorkflowStage`), `docs/research/ID-9-POSITION-SIZING-DISCOVERY-AND-V0-CONTRACT.md`
(§41/§42 corrected per that round's own §25 instruction).

## 32. `git diff --check`

Clean.

## 33. Remaining Owner decisions

(1) Whether/when to supply a real `CapitalPolicy` (total deployable
capital, risk-budget %, max-position-value %) to activate ID-9 in
production — until then, every cycle honestly reports
`CAPITAL_POLICY_UNAVAILABLE`. (2) Whether §11's `capital.json`/
`risk.json` field names should inform that future policy's exact
values, or whether the Owner prefers different numbers entirely (this
milestone invents none). (3) Whether/when persistence becomes necessary
(§21) — deferred until a genuine production/audit/API consumer exists.
(4) Whether the dormant P5.2-P5.6 pipeline should eventually be
formally retired/removed, or left as legacy-compatible dead code
indefinitely — not decided or required by this milestone. (5) Whether a
future milestone should pursue reconciling the two disjoint capital/
holdings ledgers (My Portfolio vs. legacy `owner_positions`) to support
a genuine (non-theoretical) available-capital/concentration constraint.

## 34. Final implementation classification

**ID9_V0_CORE_IMPLEMENTATION_METHODOLOGY_CORRECT_NO_PRODUCTION_ACTIVATION**
(corrected from `ID9_V0_CORE_IMPLEMENTATION_COMPLETE_NO_PRODUCTION_ACTIVATION`) —
the pure evaluator, domain contract, and canonical workflow wiring are
all implemented, tested, methodology-correct after this round's three
fixes, and source-review-ready; production sizing remains inert (every
real cycle reports `CAPITAL_POLICY_UNAVAILABLE`) until the Owner
explicitly supplies a `CapitalPolicy` — a deliberate, honest,
zero-invented-numbers default state, not an incomplete implementation.

## 35. Correction record — this round (2026-09-07)

The Owner's source review accepted the initial ID-9 V0 core
implementation's mathematics and overall architecture in substance
(everything listed in the Owner's own "keep unchanged" list in §8 of
that authorization was left untouched — see §0/§1 for what stayed the
same) and identified three narrow correctness issues before freeze,
all resolved in this same milestone, same files, no ID-9.1/ID-9.x
created:

1. **Currentness enforcement** (§0 item 1, §9, §20, §22): the prior
   version incorrectly argued same-cycle synchronous evaluation waived
   the frozen ID-7 evidence-age/session-phase currentness contract.
   Corrected by requiring a caller-supplied `CurrentnessResult` (from
   the existing, unmodified `is_currently_usable`) and gating on it
   immediately after the direction check, before capital-policy
   availability.
2. **Policy-version identity** (§0 item 2, §5, §18, §19): the prior
   version treated `policy_version` as a payload field only, excluded
   from the artifact's own composite identity, and left its presence
   rule for `NOT_SIZED` results imprecise. Corrected with a new
   `identity_tuple()` method (including `policy_version`) and a refined
   presence rule (`POLICY_PARTICIPATED_NOT_SIZED_REASON_CODES`)
   distinguishing "policy never inspected" from "policy inspected but
   the result was still refused."
3. **Silent lot-size fallback** (§0 item 3, §14): the prior version
   defaulted `lot_size` to `1` if canonical `Instrument` metadata was
   absent from the workflow's own lookup map. Corrected to raise a
   contract error instead — the absence is proven architecturally
   impossible (every instrument reaching the stage was itself sourced
   from the same `instruments` sequence), never a runtime condition to
   size around with fabricated metadata.

Additionally reviewed and confirmed correct, unchanged: `position_sizing_as_of`
semantics (§19 — genuinely the right market-time checkpoint, not merely
convenient); the evaluation-order gates-first philosophy; all sizing
mathematics (§10-17); the dormant P5.2-P5.6 disposition (§3); the
absence of any liquidity/concentration/order/execution surface (§24-25).
One wall-clock-coherence improvement was made alongside the currentness
fix (§0, §19, §22): `position_sizing_stage` now captures exactly one
`sizing_clock_instant`, reused for both the currentness `now` and this
artifact's own `evaluated_at`, proven by a dedicated spy test. 19 new
tests; 2 pre-existing tests updated (neither weakened, both re-scoped
correctly per §26); full suite **3831 passed, 1 pre-existing unrelated
skip, 0 failures**. Zero schema change; zero new persistence; zero
EMR/DarvaX/ID-6/ID-7/ID-8-methodology touch; `git diff --check` clean.

---

## 36. Capital Policy Activation round (2026-09-07) — summary

The Owner froze §0-§35 in full (`ID9_V0_CORE_IMPLEMENTATION_METHODOLOGY_CORRECT_NO_PRODUCTION_ACTIVATION`)
and authorized exactly one remaining task: resolve *why* production
still supplies `capital_policy=None` to every cycle, and prepare (never
choose) the Owner's own numeric activation decision. Nothing in §0-§35
— `PositionSizing` domain semantics, `PositionSizingV0Engine`
mathematics, currentness enforcement, composite identity, policy-
participation/provenance rules, LONG-only scope, the three quantity
formulas, binding-constraint semantics, Decimal/floor rules, lot-size
semantics, zero-quantity behavior, the dormant P5.2-P5.6 disposition,
or the persistence decision — changed in this round. This section
onward (§36-§49) documents the new, additive configuration-activation
mechanism only.

## 37. Canonical configuration seam

Inspected every real construction site of `OwnerValidationPipeline`:

- `src/athena/cli.py:241` — `_owner_validation_pipeline(repo, config_dir)`,
  a small private helper. This is the **one** place both real
  production entry points share: `_cmd_cycle` (`athena cycle`, line
  449) and `_cmd_serve`'s `HostDueRunner`-driven scheduled worker (line
  634 — the actual `--with-cycles` PID 2453 production path). No other
  code constructs the pipeline for scheduled/live use.
- Five other call sites construct `OwnerValidationPipeline` directly,
  each for a narrower, non-scheduled purpose:
  `ops/canary.py` (canary probe), `ops/config_preview.py` (dry-run
  config preview against a *candidate*, not live, config dir),
  `ops/fast_revalidation.py` (symbol-scoped fast re-validate),
  `ops/full_validation.py` (owner-triggered full-universe validation
  job), `ops/symbol_validate.py` (on-demand single-symbol validate).
  These remain **out of scope** for this round — deliberately: they are
  on-demand diagnostic/ops tools, not the scheduled cycles the Owner's
  own §11 concern ("every otherwise-valid current LONG opportunity...")
  is about, and `PositionSizing` is not persisted (§21) so an
  inconsistency between these paths' policy availability has zero
  durable effect today. If the Owner later wants sizing evidence from
  these tools too, they can each be pointed at the same
  `load_position_sizing_policy_config` loader with a one-line change —
  no new seam would be needed.

`_owner_validation_pipeline` was chosen as the seam (rather than, say,
loading policy inside `OwnerValidationPipeline.__init__` itself)
because `__init__` already accepts an optional `capital_policy`
parameter (added in the V0 core-implementation round) and is exercised
directly, with an explicit `capital_policy=None`/a test-constructed
policy, by 17 existing ID-9 tests plus dozens of pre-ID-9 tests — making
`__init__` auto-load from disk would silently change what "pass
`capital_policy=None`" means for every one of those call sites.
Extending the one already-existing construction helper instead touches
zero test fixtures and leaves `OwnerValidationPipeline.__init__`
byte-for-byte unchanged.

```python
# src/athena/cli.py
def _owner_validation_pipeline(repo: SqliteRepository, config_dir: Path):
    from athena.intraday.position_sizing_config import load_position_sizing_policy_config
    from athena.ops.owner_validation import OwnerValidationPipeline

    return OwnerValidationPipeline(
        repo, config_dir, capital_policy=load_position_sizing_policy_config(config_dir)
    )
```

## 38. Exact config shape / template

New file, `config/position_sizing_policy.json` (does **not** exist in
production today — §39/§44). New module,
`src/athena/intraday/position_sizing_config.py` (own `_Strict` pydantic
base, own loader — deliberately not joined to
`athena.config.loader.load_config`'s all-files-mandatory aggregate
tree, since this file must be able to be absent without breaking every
other `athena` command). Exactly four fields, matching `CapitalPolicy`
1:1 — no sector/liquidity/daily-loss/portfolio-exposure/broker-cash/
margin/leverage/score/confidence/RR field was added:

```json
{
  "_meta": {
    "description": "ID-9 V0 CapitalPolicy — explicit Owner-approved capital/risk policy for live position sizing. Percentages are percent-numbers (0.5 means 0.5%, never 50%). All three numeric fields MUST be JSON strings (exact Decimal parsing — never a bare JSON number)."
  },
  "total_deployable_capital": "<INR amount, e.g. \"500000.00\">",
  "risk_budget_per_trade_pct": "<percent-number in (0, 100], e.g. \"0.50\">",
  "max_position_value_pct": "<percent-number in (0, 100], e.g. \"15.00\">",
  "policy_version": "<non-empty Owner-chosen identifier, e.g. \"policy-2026-09-07-v1\">"
}
```

Units (§5 of the authorization): `total_deployable_capital` is a plain
INR amount. `risk_budget_per_trade_pct`/`max_position_value_pct` reuse
`CapitalPolicy`'s own already-frozen percent-*number* convention
exactly (`Decimal("0.5")` means 0.5%, never a 0-1 fraction, never 50%).
All three numeric fields must be JSON strings, not bare JSON numbers —
`PositionSizingPolicyConfig` rejects a bare number outright (§41) so
that Decimal parsing is always exact, never routed through a `float`
intermediate.

No duplicate alias was created: the file is intentionally named
`position_sizing_policy.json`, never `sizing.json` (the existing,
confirmed-dormant P5.3 legacy config) or `capital.json`/`risk.json`
(confirmed dormant by the ID-9 discovery report) — a future reader must
never be able to mistake this for, or a replacement of, one of those.

## 39. Absent-policy production behavior

`load_position_sizing_policy_config(config_dir)`:

- File absent → returns `None`. This is not an error — it is the exact
  same production-safe default `OwnerValidationPipeline.__init__`
  already treats `capital_policy=None` as: every ID-9 sizing
  observation continues to honestly report `CAPITAL_POLICY_UNAVAILABLE`,
  completely unchanged from before this round.
- File present and valid → constructs exactly **one** immutable
  `CapitalPolicy` instance, injected once at `OwnerValidationPipeline`
  construction and reused for every instrument in the scan (proven by
  `test_id9_one_capital_policy_instance_reused_across_multiple_instruments`,
  §45 — the exact same policy object, checked by identity, reaches
  `PositionSizingV0Engine.evaluate` for two independent instruments in
  one run).
- File present and invalid (bad JSON, wrong type, unknown key, an
  out-of-range value, a bare-number percentage) → raises `ConfigError`
  loudly. A malformed policy file must never silently fall back to
  `None` (which would misreport a genuine operator typo as "not yet
  configured") and must never clamp/default/reinterpret a bad value.

## 40. Policy-version semantics (operational rule)

`policy_version` is Owner-controlled **policy** identity — already
frozen (§0 item 2, §5, §18, §19 above) as independent of
`sizing_methodology_version` (`DEFAULT_METHODOLOGY_VERSION =
"position-sizing-v0"`, the sizing **mathematics** identity). This round
adds no new field or persistence for this — the operational discipline
is documented, not (and per the authorization's own §6, deliberately
not) enforced by a policy registry:

> **Whenever any effective policy value changes, the Owner/operator
> must also supply a new `policy_version`.**

A stateless, single-file loader has no prior value to diff against, so
building a fingerprint/version-relationship check would require
persistent state — explicitly out of scope for this milestone (§6:
"must NOT build a policy registry or persistence subsystem merely for
this"). `test_id9_changing_policy_does_not_change_sizing_methodology_version`
(§45) proves the two identities stay independent: two runs of the same
scan under `policy-v1`/`policy-v2` report the identical
`sizing_methodology_version` and different `policy_version`s, exactly
as `PositionSizing.identity_tuple()` (§5/§19, unchanged) already
requires.

## 41. Configuration validation

`PositionSizingPolicyConfig` (pydantic, `extra="forbid"`) rejects, with
a clear `ConfigError` message naming the file and field:

- `total_deployable_capital <= 0`
- `risk_budget_per_trade_pct <= 0` or `> 100`
- `max_position_value_pct <= 0` or `> 100`
- empty/whitespace-only/missing `policy_version`
- any unknown key (a typo must fail loudly, never silently ignored) —
  including an underscore-prefixed one (§41a hardening below)
- a bare JSON number for any of the three numeric fields (must be a
  JSON string — exact `Decimal` parsing, never a float intermediate)
- non-JSON / non-object top-level content

No clamping, no fallback value, no percentage reinterpretation, no
float conversion path exists anywhere in the loader. On success, the
loader additionally constructs a real `CapitalPolicy(...)` from the
validated fields — `CapitalPolicy.__post_init__`'s own frozen
invariants (§the V0 core round) run a second time, for real, rather
than being duplicated as a parallel range check only.

### 41a. Final config hardening (2026-09-07)

Owner/Chief Architect source review accepted the whole activation
architecture (§37-§40 above) and found two narrow config-hardening
gaps before Owner values are written — both fixed in this same
milestone, same file, no ID-9.1/ID-9.x created:

1. **Strict meta-key handling.** The original `_Strict._drop_meta_keys`
   dropped *every* key starting with `_` before validation — directly
   contradicting this module's own "unknown keys are errors" contract,
   since a typo like `_metaa`, `_unexpected`, or even
   `_risk_budget_per_trade_pct` would be silently swallowed instead of
   rejected. Replaced with `_DOCUMENTATION_KEYS = frozenset({"_meta",
   "_note"})` and `_drop_documentation_keys`, which drops only those
   two exact keys — every other key, underscore-prefixed or not, now
   reaches pydantic's `extra="forbid"` and fails loudly.
2. **Policy-version normalization.** `_non_empty_version` validated
   `v.strip()` for emptiness but returned the original, untrimmed `v`
   — so `"capital-policy-v1"` and `" capital-policy-v1 "` (a stray
   leading/trailing space in the JSON file) would be accepted as two
   *different* `policy_version` identities, silently splitting
   `PositionSizing.identity_tuple()` (§19/§40) for what the Owner
   intended as the same policy. Fixed to return `stripped` — trims
   surrounding whitespace only, never lowercases, never rewrites
   interior characters.

Neither fix touches `CapitalPolicy` itself, the activation seam
(`cli.py`'s `_owner_validation_pipeline`), the config file shape (§38),
or any sizing methodology (§0-§35, unchanged). **8 new tests** added to
`tests/market_intel/test_position_sizing_config.py` (39 total, up from
31): `_meta` accepted, `_note` accepted, an arbitrary `_unknown` key
rejected, a misspelled `_metaa` rejected, an ordinary unknown key still
rejected, surrounding whitespace trimmed, whitespace-only version
rejected, and a direct `PositionSizingPolicyConfig` normalization
proof. Full suite **3876 passed, 1 pre-existing unrelated skip, 0
failures** (up from 3868, exactly +8). Zero schema/production change;
`config/position_sizing_policy.json` still does not exist in
production; `git diff --check` clean, diff scoped to
`position_sizing_config.py` and its test file only.

## 42. Normalized Owner Policy Impact Table

Non-prescriptive — for understanding policy *behavior* only, never a
recommendation, never calibrated against ID-8 outcomes. Generated by
calling the real, frozen `PositionSizingV0Engine.evaluate` (never
hand-derived arithmetic) against a synthetic normalized LONG
`EntryActionability` fixture: `entry_reference = ₹100`,
`total_deployable_capital = ₹10,00,000`, `instrument_lot_size = 1`
(illustrative — real production lot sizes are per-instrument, §14).
Three per-share-risk geometries (LOW = ₹1/share = 1% of entry, MEDIUM =
₹2/share = 2%, WIDE = ₹4/share = 4%) × the specified 3×3
`risk_budget_per_trade_pct` × `max_position_value_pct` matrix:

| Risk-per-share | risk_budget_per_trade_pct | max_position_value_pct | Risk budget (₹) | Risk qty | Max-value qty | Theoretical-capital qty | Recommended qty | Recommended value (₹) | Capital at risk (₹) | Binding constraint(s) |
|---|---|---|---|---|---|---|---|---|---|---|
| LOW (₹1/share) | 0.25% | 10% | 2500.00 | 2500 | 1000 | 10000 | 1000 | 100000.00 | 1000.00 | MAX_POSITION_VALUE |
| LOW (₹1/share) | 0.25% | 15% | 2500.00 | 2500 | 1500 | 10000 | 1500 | 150000.00 | 1500.00 | MAX_POSITION_VALUE |
| LOW (₹1/share) | 0.25% | 20% | 2500.00 | 2500 | 2000 | 10000 | 2000 | 200000.00 | 2000.00 | MAX_POSITION_VALUE |
| LOW (₹1/share) | 0.50% | 10% | 5000.00 | 5000 | 1000 | 10000 | 1000 | 100000.00 | 1000.00 | MAX_POSITION_VALUE |
| LOW (₹1/share) | 0.50% | 15% | 5000.00 | 5000 | 1500 | 10000 | 1500 | 150000.00 | 1500.00 | MAX_POSITION_VALUE |
| LOW (₹1/share) | 0.50% | 20% | 5000.00 | 5000 | 2000 | 10000 | 2000 | 200000.00 | 2000.00 | MAX_POSITION_VALUE |
| LOW (₹1/share) | 1.00% | 10% | 10000.00 | 10000 | 1000 | 10000 | 1000 | 100000.00 | 1000.00 | MAX_POSITION_VALUE |
| LOW (₹1/share) | 1.00% | 15% | 10000.00 | 10000 | 1500 | 10000 | 1500 | 150000.00 | 1500.00 | MAX_POSITION_VALUE |
| LOW (₹1/share) | 1.00% | 20% | 10000.00 | 10000 | 2000 | 10000 | 2000 | 200000.00 | 2000.00 | MAX_POSITION_VALUE |
| MEDIUM (₹2/share) | 0.25% | 10% | 2500.00 | 1250 | 1000 | 10000 | 1000 | 100000.00 | 2000.00 | MAX_POSITION_VALUE |
| MEDIUM (₹2/share) | 0.25% | 15% | 2500.00 | 1250 | 1500 | 10000 | 1250 | 125000.00 | 2500.00 | RISK_BUDGET |
| MEDIUM (₹2/share) | 0.25% | 20% | 2500.00 | 1250 | 2000 | 10000 | 1250 | 125000.00 | 2500.00 | RISK_BUDGET |
| MEDIUM (₹2/share) | 0.50% | 10% | 5000.00 | 2500 | 1000 | 10000 | 1000 | 100000.00 | 2000.00 | MAX_POSITION_VALUE |
| MEDIUM (₹2/share) | 0.50% | 15% | 5000.00 | 2500 | 1500 | 10000 | 1500 | 150000.00 | 3000.00 | MAX_POSITION_VALUE |
| MEDIUM (₹2/share) | 0.50% | 20% | 5000.00 | 2500 | 2000 | 10000 | 2000 | 200000.00 | 4000.00 | MAX_POSITION_VALUE |
| MEDIUM (₹2/share) | 1.00% | 10% | 10000.00 | 5000 | 1000 | 10000 | 1000 | 100000.00 | 2000.00 | MAX_POSITION_VALUE |
| MEDIUM (₹2/share) | 1.00% | 15% | 10000.00 | 5000 | 1500 | 10000 | 1500 | 150000.00 | 3000.00 | MAX_POSITION_VALUE |
| MEDIUM (₹2/share) | 1.00% | 20% | 10000.00 | 5000 | 2000 | 10000 | 2000 | 200000.00 | 4000.00 | MAX_POSITION_VALUE |
| WIDE (₹4/share) | 0.25% | 10% | 2500.00 | 625 | 1000 | 10000 | 625 | 62500.00 | 2500.00 | RISK_BUDGET |
| WIDE (₹4/share) | 0.25% | 15% | 2500.00 | 625 | 1500 | 10000 | 625 | 62500.00 | 2500.00 | RISK_BUDGET |
| WIDE (₹4/share) | 0.25% | 20% | 2500.00 | 625 | 2000 | 10000 | 625 | 62500.00 | 2500.00 | RISK_BUDGET |
| WIDE (₹4/share) | 0.50% | 10% | 5000.00 | 1250 | 1000 | 10000 | 1000 | 100000.00 | 4000.00 | MAX_POSITION_VALUE |
| WIDE (₹4/share) | 0.50% | 15% | 5000.00 | 1250 | 1500 | 10000 | 1250 | 125000.00 | 5000.00 | RISK_BUDGET |
| WIDE (₹4/share) | 0.50% | 20% | 5000.00 | 1250 | 2000 | 10000 | 1250 | 125000.00 | 5000.00 | RISK_BUDGET |
| WIDE (₹4/share) | 1.00% | 10% | 10000.00 | 2500 | 1000 | 10000 | 1000 | 100000.00 | 4000.00 | MAX_POSITION_VALUE |
| WIDE (₹4/share) | 1.00% | 15% | 10000.00 | 2500 | 1500 | 10000 | 1500 | 150000.00 | 6000.00 | MAX_POSITION_VALUE |
| WIDE (₹4/share) | 1.00% | 20% | 10000.00 | 2500 | 2000 | 10000 | 2000 | 200000.00 | 8000.00 | MAX_POSITION_VALUE |

This table describes how the three V0 constraints interact under
different policy choices — it does not say any row is safe, aggressive,
conservative, or optimal, and it was not fit or checked against any
ID-8 hit-rate/MFE/MAE/bootstrap evidence.

## 43. Mathematical theoretical-capital-binding note

Confirmed, exactly as already discovered and frozen in the V0 core
round (§13): `theoretical_capital_quantity` is **10000 in every single
row above** — it never becomes the unique tightest constraint anywhere
in this matrix, because `max_position_value_pct <= 20%` in every tested
combination keeps `max_value_quantity <= theoretical_capital_quantity`
by construction. This is not a limitation of the sample matrix; it is
the already-proven general property (`max_position_value_pct <= 100%`
is enforced by `CapitalPolicy.__post_init__`) that
`THEORETICAL_CAPITAL` can only ever **co-bind** with
`MAX_POSITION_VALUE`, and only at the 100%-deployment boundary — see
`test_theoretical_capital_co_binds_with_max_value_at_full_deployment`
in `tests/market_intel/test_position_sizing_engine.py`, unchanged by
this round. No synthetic unique-theoretical-capital-binding example was
manufactured for this table, per the authorization's own instruction.

## 44. Proof dormant configs remain unused

`config/capital.json` (`CapitalConfig`) and `config/risk.json`
(`RiskConfig`) are not read, imported, or referenced anywhere in
`position_sizing_config.py` — proven by a dedicated source-scan test,
`test_source_never_reads_capital_or_risk_json_filenames`, and further
proven behaviorally by `test_dormant_capital_and_risk_json_never_imported`
(real `capital.json`/`risk.json`-shaped files present in the same
`config_dir`, with no `position_sizing_policy.json`, still yields
`None`). Zero values from either file were used anywhere in this
round's implementation, tests, or the impact table above (§42 uses only
the Owner-message-specified normalized figures). `config/sizing.json`
(the dormant P5.3 legacy sizing config, a different dormant file from
the two named above) is likewise never read — no test or code in this
round references it at all.

## 45. Tests

**31 new tests**, `tests/market_intel/test_position_sizing_config.py`
(pure config-loader unit tests): missing-file → `None` (2), valid
config constructs `CapitalPolicy` (1), exact `policy_version`
propagation (1), Decimal-exact parsing with no float drift (1), bare
JSON number rejected for each of the three numeric fields (3,
parametrized), repeated loads produce an equal policy (1), invalid
JSON / non-object JSON (2), unknown key rejected (1), invalid
capital/risk-pct/max-value-pct rejected (3 groups, parametrized, 11
total cases), empty/missing `policy_version` rejected (3), dormant
`capital.json`/`risk.json` present-but-unread (1), source-scan proof
neither dormant config nor `CapitalConfig`/`RiskConfig` is referenced
(1), source-scan proof of zero `orders`/`brokers`/`execution`/
`allocation`/`sizing`/network imports (1), a real-socket-`connect`
monkeypatch proof the loader makes no network call (1), and a
`PositionSizingPolicyConfig`-level `_meta`-key-drop proof (1).

**6 new tests**, `tests/ops/test_owner_validation.py` (workflow-seam
integration): `cli._owner_validation_pipeline` defaults to
`capital_policy=None` when the config file is absent; the same seam
constructs and injects a real `CapitalPolicy` when the file is present
and valid; the same seam raises `ConfigError` (never falls back to
`None`) when the file is present but invalid; one real `CapitalPolicy`
instance is reused (checked by object identity through a spy on
`PositionSizingV0Engine.evaluate`) across two real, independently
forced TRADE+QUALIFIED+ACTIONABLE instruments in one scan; two full
scans under `policy-v1`/`policy-v2` report identical
`sizing_methodology_version` and differing `policy_version`; a
source-scan proof that neither `cli.py` nor `position_sizing_config.py`
imports `athena.orders`/`athena.brokers`/`athena.execution`.

None of the 61 pre-existing ID-9 tests (34 pure-engine/domain + 8
workflow from the V0 core round, plus 19 pure-engine/domain-model
currentness/policy-identity tests from the correction round) were
weakened, removed, or re-scoped — all still pass unchanged.

**8 more new tests** (§41a config hardening, same file,
`tests/market_intel/test_position_sizing_config.py`, now 39 total):
`_meta` accepted/ignored, `_note` accepted/ignored, an arbitrary
`_unknown` key rejected, a misspelled `_metaa` rejected, an ordinary
unknown key still rejected, `policy_version` surrounding whitespace
trimmed, whitespace-only `policy_version` rejected, and a direct
`PositionSizingPolicyConfig` normalization proof.

## 46. Full suite

**3876 passed, 1 pre-existing unrelated skip, 0 failures** (up from
3831 before this round — exactly +45: 39 config-loader tests + 6
workflow-seam tests).

## 47. `git diff --check`

Clean. Diff scoped to exactly: `src/athena/cli.py` (the seam, ~10 lines),
`tests/ops/test_owner_validation.py` (6 new tests), plus two new files
— `src/athena/intraday/position_sizing_config.py` and
`tests/market_intel/test_position_sizing_config.py`. No file outside
this set is touched; no unrelated pre-existing test was edited.

## 48. Schema/PID/production safety

- `db/athena.db`: zero writes performed by this round (config loading
  is pure file I/O). `PRAGMA integrity_check` → `ok`; `entry_actionabilities`
  row count unchanged from before this round; `SCHEMA_VERSION` constant
  in `schema.py` untouched at `18` — no migration, no `schema.py` diff.
- Production PID `2453` (`athena.cli serve --with-cycles`) left running
  untouched throughout — no restart, no `Validate All`, no manual cycle
  triggered.
- No order/broker/execution call — proven by source-scan test (§45) —
  and no network/provider call for policy loading (proven by a real
  `socket.connect` monkeypatch failing the test if ever invoked, §45).
- `config/position_sizing_policy.json` was **not** created in this
  round — production `capital_policy` remains `None`,
  `CAPITAL_POLICY_UNAVAILABLE` remains the honest live result, exactly
  as before.
- EMR (`db/emr.db`, the EM-7 worker) and DarvaX (`db/darvax.db`)
  untouched — this round never imports either package.

## 49. Exact remaining Owner values / activation procedure

**Four values are still required from the Owner before ID-9 can
produce a real recommended quantity in production:**

- **(A) `total_deployable_capital`** — an INR amount, e.g. `"500000.00"`.
- **(B) `risk_budget_per_trade_pct`** — a percent-number in `(0, 100]`,
  e.g. `"0.50"` (meaning 0.5%).
- **(C) `max_position_value_pct`** — a percent-number in `(0, 100]`,
  e.g. `"15.00"` (meaning 15%).
- **(D) `policy_version`** — a non-empty identifier, e.g.
  `"policy-2026-09-07-v1"`. Per §40, any future change to (A)/(B)/(C)
  must be paired with a new value here.

**Activation procedure, once the Owner supplies all four:**

1. Create `config/position_sizing_policy.json` with those four values,
   using the exact template in §38 (all three numeric fields as JSON
   strings).
2. No code change, no restart of PID 2453 is required for the next
   scheduled cycle to pick it up — `_owner_validation_pipeline` loads
   the file fresh on every `OwnerValidationPipeline` construction
   (once per `_cmd_cycle` invocation / once per `HostDueRunner`-driven
   cycle), so the very next PREMARKET/REFRESH/CLOSING cycle after the
   file is written will use it. (A live-serving process reconstructs
   its `OwnerValidationPipeline` per cycle via this same helper — no
   in-memory caching to invalidate.)
3. This activation step is a tiny, reversible configuration change —
   not a methodology milestone. Deleting or emptying the file at any
   time instantly reverts to `CAPITAL_POLICY_UNAVAILABLE`, with zero
   code change.
4. `PositionSizing` remains non-persisted (§21, unchanged) — activation
   makes the pure per-cycle sizing result available in
   `WorkflowContext` for that cycle's own consumers; it does not, by
   itself, add any new persisted row, API endpoint, or dashboard
   surface.

---

**ID-9 CAPITAL POLICY CONFIG HARDENED — READY FOR OWNER VALUES / FINAL
ACTIVATION**
