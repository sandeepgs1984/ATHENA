# ID-9 — Position Sizing V0 Core Implementation

Status: **ID-9 POSITION SIZING V0 CORE IMPLEMENTATION READY FOR OWNER /
CHIEF ARCHITECT REVIEW.**

## 1. Executive verdict

A new, pure, deterministic V0 position-sizing engine
(`PositionSizingV0Engine`) and its immutable domain contract
(`PositionSizing`, `CapitalPolicy`) are implemented under
`src/athena/intraday/` — the same package `EntryQualification`/
`EntryActionability` live in — consuming `EntryActionability` directly
per the frozen Owner discovery decision (§2). LONG-only, three
independent capital constraints (risk-budget, max-position-value,
theoretical-deployable-capital), quantity always floored to whole lots,
never forced to a minimum, zero score/RR/confidence-weighted scaling of
any kind. A new `position_sizing` `WorkflowStage` wires it into the
canonical per-instrument DAG, `depends_on=("entry_actionability",)`,
consuming the exact same-cycle artifact — no persistence yet
(`PERSISTENCE_NOT_YET_REQUIRED`, §21), no capital policy read from
dormant config (`self._capital_policy` defaults to `None`, meaning every
real cycle today honestly reports `CAPITAL_POLICY_UNAVAILABLE` until the
Owner explicitly wires one). The dormant P5.2/P5.3 pipeline is left
completely untouched and is not imported by any ID-9 file (§3). 42 new
tests; full suite **3812 passed, 1 pre-existing unrelated skip, 0
failures**. Zero schema/production changes; `db/athena.db` confirmed
unchanged (schema 18, integrity ok); PID 2453 untouched; zero order/
broker/execution activation; zero EMR/DarvaX touch.

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
identity = the entire upstream `EntryActionability` composite key
copied verbatim (`instrument_id`, `session_date`,
`entry_qualification_as_of`, `decision_id`,
`entry_qualification_methodology_version`, `entry_actionability_as_of`,
`entry_actionability_methodology_version`) plus this artifact's own
`position_sizing_as_of`/`sizing_methodology_version` — no surrogate id,
mirroring `EntryActionability`'s own frozen identity model exactly.
Two independent field-presence rules (never conflated): upstream-echoed
risk-geometry fields (`direction`, `entry_reference_price`,
`operative_invalidation_level`, `per_share_risk`) present whenever
`UPSTREAM_NOT_ACTIONABLE` is not in `reason_codes`; capital-derived and
result fields present iff `state in (SIZED, ZERO_QUANTITY_UNDER_POLICY)`.
`__post_init__` enforces both rules plus the derived-value invariants of
§13, mirroring `EntryActionability.__post_init__`'s own "reject an
untruthful supplied combination" philosophy (17 dedicated domain-
construction tests, §23).

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
independent concepts, per instruction). 4 dedicated tests (§23).

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
repository read) via a new `instrument_by_id` map, defaulting to `1`
only for an instrument absent from that mapping (should not occur in
practice). Never hardcoded to `1` in the engine itself — `_floor_to_lot`
takes `lot_size` as a genuine parameter and is tested with a non-1 lot
size (`instrument_lot_size=7`) to prove the flooring logic is generic,
not merely "always divides by 1." `ROUND_DOWN`/floor only, everywhere —
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
CAPITAL_POLICY_UNAVAILABLE, INVALID_RISK_GEOMETRY}`,
`ZERO_QUANTITY_REASON_CODES = {ZERO_QUANTITY_UNDER_POLICY}`. `SIZED`
requires empty `reason_codes` (mirroring `ACTIONABLE`'s own "not
blocked" invariant). Every mapping from the Owner's own §16 examples
(upstream not ACTIONABLE → NOT_SIZED; SHORT/NONE → NOT_SIZED +
UNVALIDATED_DIRECTION; policy missing → NOT_SIZED + CAPITAL_POLICY_UNAVAILABLE;
invalid geometry → NOT_SIZED + INVALID_RISK_GEOMETRY; quantity floors
below lot → ZERO_QUANTITY_UNDER_POLICY; valid positive quantity → SIZED)
is implemented exactly and independently tested.

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
re-evaluation capability. `sizing_methodology_version =
DEFAULT_METHODOLOGY_VERSION = "position-sizing-v0"`, minted and frozen
here, independent of `policy_version` (§6/§18's own explicit separation).
`evaluated_at` is the one captured wall-clock instant, reused from the
same `self._persistence_clock()` `entry_actionability_stage` already
uses — never a second clock source.

## 20. Currentness

**Not implemented as a separate module in this milestone**, per §18's
own explicit sequencing: since no persistence exists yet
(`PERSISTENCE_NOT_YET_REQUIRED`, §21), there is no "read a stored result
later and ask whether it's still usable" scenario to serve — the
evaluator always runs fresh, synchronously, within the same cycle that
produced its upstream `EntryActionability`. If a future milestone adds
persistence, currentness should mirror
`entry_actionability_currentness.is_currently_usable`'s own exact
pattern: a pure, injected-`now` function checking (a) the bound
`EntryActionability`'s own current-usability, (b) exact
`policy_version` match against whatever the caller asserts is the
current policy, and (c) exact upstream `EntryActionability` identity
match — never a new, unrelated freshness clock, and never a sticky
"sized" state that survives the underlying opportunity being
superseded. This is a design note for that future milestone, not
speculative code shipped now.

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

**42 new tests.** `tests/market_intel/test_position_sizing_engine.py`
(34): valid LONG sizing, risk-budget binding, max-position-value
binding, theoretical-capital co-binding (§13's own mathematical
finding), two-way co-binding, lot-size floor (non-1 lot), zero-quantity-
never-forced, derived-value invariants, SHORT refused, NONE refused
(contract error, §9), missing-policy refused, upstream-not-actionable
refused (without reading geometry), invalid-geometry refused
(defensive), naive-`evaluated_at`/sub-1-lot-size rejection, Decimal-
only-arithmetic, exact-provenance, policy-version-echo, deterministic
repeat, RR/T1/T2-never-read (source scan + behavioral), no-provider/
persistence/legacy-pipeline-import (source scans), 11 domain-model
construction/rejection tests, 3 `CapitalPolicy` validation tests.
`tests/ops/test_owner_validation.py` (8): DAG order preservation,
transitive dependency, out-of-scope-Decision non-invocation (call-count
spy), WATCH-reaches-`UPSTREAM_NOT_ACTIONABLE`, no-policy-by-default
(`CAPITAL_POLICY_UNAVAILABLE` end-to-end), policy-injected produces
`SIZED` with exact same-cycle `EntryActionability` identity proof, no-
persistence/no-provider source scan, no-latest-repository-query source
scan. One pre-existing test (`test_id7e1_no_dag_change`) had its own
locked-in literal-count assertion updated (4→9) with an explanation of
exactly why the new, deliberate count is correct — no other pre-existing
test was touched.

## 27. Full suite

**3812 passed, 1 pre-existing unrelated skip, 0 failures** (up from
3770 before this milestone — exactly +42).

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

Created: `src/athena/intraday/position_sizing_models.py`,
`src/athena/intraday/position_sizing_engine.py`,
`tests/market_intel/test_position_sizing_engine.py`,
`docs/research/ID-9-POSITION-SIZING-V0-CORE-IMPLEMENTATION.md` (this
report). Modified: `src/athena/intraday/__init__.py` (new exports),
`src/athena/ops/owner_validation.py` (new `capital_policy` constructor
parameter, `instrument_by_id` lookup map, `position_sizing_stage`, new
`WorkflowStage`), `tests/ops/test_owner_validation.py` (8 new tests + 1
updated literal-count assertion), `docs/research/ID-9-POSITION-SIZING-DISCOVERY-AND-V0-CONTRACT.md`
(§41/§42 corrected per this milestone's §25 instruction). Tracking-doc
updates for THIS milestone (`docs/MILESTONES.md`, `ATHENA_BRIEFING.md`,
`IMPLEMENTATION_SUMMARY.md`, `docs/ATHENA-ID-TRACK-HANDOFF.md`) are
listed in this same commit's own accounting, per the mandatory
milestone-tracking workflow. Zero schema/repository/config file
touched.

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

**ID9_V0_CORE_IMPLEMENTATION_COMPLETE_NO_PRODUCTION_ACTIVATION** — the
pure evaluator, domain contract, and canonical workflow wiring are all
implemented, tested, and source-review-ready; production sizing remains
inert (every real cycle reports `CAPITAL_POLICY_UNAVAILABLE`) until the
Owner explicitly supplies a `CapitalPolicy` — a deliberate, honest,
zero-invented-numbers default state, not an incomplete implementation.

---

**ID-9 POSITION SIZING V0 CORE IMPLEMENTATION READY FOR OWNER / CHIEF
ARCHITECT REVIEW**
