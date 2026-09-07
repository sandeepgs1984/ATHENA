"""Position Sizing domain contracts (ID-9 V0).

Answers, for one already-`ACTIONABLE` opportunity: how much capital
should ATHENA recommend allocating? One layer downstream of
`EntryActionability` (ADR-013's layer 3 continues here as ID-9's own
layer 4 — WHEN/entry/risk from ID-7/ID-8, HOW MUCH here) — mirrors that
artifact's own frozen dimension discipline (persisted methodology
result vs. read-time currentness vs. policy availability vs.
direction-validation status, never conflated) and its own
`__post_init__` "reject an untruthful supplied combination" philosophy,
per ADR-015/ID-7A.1/ID-7A.2's own established precedent.

Frozen by the Owner's ID-9 V0 core-implementation authorization
(2026-09-07), following the ID-9 discovery report
(`docs/research/ID-9-POSITION-SIZING-DISCOVERY-AND-V0-CONTRACT.md`):

- Production upstream artifact: `EntryActionability` directly (state ==
  `ACTIONABLE`) — no new `EntryRisk` artifact, no research-harness
  consumption.
- V0 direction scope: LONG only — `LONG_VALIDATED_SHORT_UNVALIDATED`
  means SHORT (and the structurally-unreachable `NONE`) must never
  receive a recommended quantity; a SHORT-direction `ACTIONABLE`
  opportunity is deliberately refused, not sized-and-labeled.
- Capital mode: `THEORETICAL_POLICY_CAPITAL_SIZING` — an explicit,
  Owner-supplied `CapitalPolicy` only; ATHENA has no live broker cash/
  margin/account-balance capability (confirmed by discovery), so V0
  never subtracts `owner_positions`/My Portfolio holdings/broker
  positions from `total_deployable_capital`.
- Sizing constraints: risk-budget quantity, max-position-value
  quantity, theoretical-deployable-capital quantity — the minimum of
  the three, applicable candidates only. No liquidity/concentration/
  aggregate-portfolio-risk gate exists in V0 (discovery classified
  these `NOT_AVAILABLE`/`CONTEXT_ONLY`/`OUT_OF_V0`).
- `GOAL_BANDS_ONLY`/`RR_INFORMATIONAL_ONLY` preserved: no field here is
  ever multiplied by RR, Decision score, confidence, conviction, RS,
  RVOL, T1/T2 attractiveness, or historical hit rate. V0 sizing is a
  pure risk/capital-constraint minimum, full stop.
- Existing `CapitalConfig`/`RiskConfig` (`config/capital.json`/
  `config/risk.json`) are NOT read here, and their currently-configured
  numeric values are NOT implicitly Owner-approved V0 policy (discovery
  found both are loaded but consumed by zero engines anywhere) — this
  module accepts only an explicit, caller-supplied `CapitalPolicy`
  instance; a `None` policy is a legitimate, honestly-reported
  `CAPITAL_POLICY_UNAVAILABLE` result, never a silently-defaulted one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum, unique

from athena.domain.enums import Direction

#: ID-9-minted V0 methodology version — namespaced apart from
#: `EntryActionability`'s own `DEFAULT_METHODOLOGY_VERSION`
#: ("entry-actionability-v0"), following the exact same convention.
#: Immutable once any production row/consumer exists.
DEFAULT_METHODOLOGY_VERSION = "position-sizing-v0"

#: Monetary/quantity Decimal quantization — 2 decimal places (rupees),
#: always rounded DOWN, mirroring the existing `_quantize` conventions
#: in `brokers/engine.py`/`darvax/signals/stops.py`, but always
#: ROUND_DOWN here (never `ROUND_HALF_UP`) since a sizing/budget figure
#: must never be inflated by rounding — an owner's stated risk budget
#: or position-value cap is a ceiling, not a target to round toward.
MONEY_PLACES = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class CapitalPolicy:
    """Explicit, Owner-supplied capital policy — deliberately NOT loaded
    from `config/capital.json`/`config/risk.json` (ID-9 discovery found
    both dormant, consumed by zero engines; their currently-configured
    values are not implicitly Owner-approved V0 policy). A thin,
    V0-minimal view reusing `CapitalConfig`/`RiskConfig`'s own field
    *semantics* (`total_capital`, `per_trade_risk_pct`) and naming
    conventions (percent numbers, e.g. ``Decimal("0.5")`` meaning 0.5%,
    never a 0-1 fraction) without reusing those pydantic config-loader
    classes directly — this avoids both carrying V0-irrelevant fields
    (`max_capital_per_sector_pct`, `max_daily_loss_pct`, ...) into a
    "keep V0 minimal" contract, and silently coupling to file-based
    config loading. `policy_version` is independent of
    `sizing_methodology_version` (`DEFAULT_METHODOLOGY_VERSION`,
    frozen module constant): a policy-value change (e.g. the Owner
    raising `risk_budget_per_trade_pct`) must never masquerade as a
    methodology-version change, and vice versa."""

    total_deployable_capital: Decimal
    risk_budget_per_trade_pct: Decimal
    max_position_value_pct: Decimal
    policy_version: str

    def __post_init__(self) -> None:
        if self.total_deployable_capital <= 0:
            raise ValueError("CapitalPolicy.total_deployable_capital must be positive")
        if not (0 < self.risk_budget_per_trade_pct <= 100):
            raise ValueError(
                "CapitalPolicy.risk_budget_per_trade_pct must be in (0, 100], got "
                f"{self.risk_budget_per_trade_pct}"
            )
        if not (0 < self.max_position_value_pct <= 100):
            raise ValueError(
                "CapitalPolicy.max_position_value_pct must be in (0, 100], got "
                f"{self.max_position_value_pct}"
            )
        if not self.policy_version:
            raise ValueError("CapitalPolicy.policy_version is mandatory")


@unique
class PositionSizingState(str, Enum):
    """Persisted-shape, evaluation-time-only methodology verdict —
    deliberately three values only, mirroring `EntryActionabilityState`'s
    own minimal discipline. No `UNKNOWN` member: every V0 failure mode
    maps truthfully to one of these three (a genuine gap would require a
    real, deterministic case this mapping cannot express — none was
    found in V0 design)."""

    SIZED = "SIZED"
    NOT_SIZED = "NOT_SIZED"
    ZERO_QUANTITY_UNDER_POLICY = "ZERO_QUANTITY_UNDER_POLICY"


@unique
class PositionSizingReasonCode(str, Enum):
    """Reason vocabulary, family-separated exactly like
    `EntryActionabilityReasonCode` — a `NOT_SIZED` verdict draws only
    from `NOT_SIZED_REASON_CODES`; `ZERO_QUANTITY_UNDER_POLICY` draws
    only from `ZERO_QUANTITY_REASON_CODES`; `SIZED` carries none."""

    UPSTREAM_NOT_ACTIONABLE = "UPSTREAM_NOT_ACTIONABLE"
    UNVALIDATED_DIRECTION = "UNVALIDATED_DIRECTION"
    #: Owner correction, 2026-09-07: `EntryActionability.state == ACTIONABLE`
    #: is a persisted, evaluation-time-only methodology verdict (ID-7A0.1's
    #: own frozen dimension A) — it does NOT mean the artifact is currently
    #: usable for a LIVE recommendation right now. This reason means the
    #: bound `EntryActionability` failed the existing, unmodified ID-7
    #: `entry_actionability_currentness.is_currently_usable(...)` contract
    #: (superseded identity, stale evidence, or a non-REGULAR session) —
    #: never a reimplementation of that rule.
    UPSTREAM_NOT_CURRENT = "UPSTREAM_NOT_CURRENT"
    CAPITAL_POLICY_UNAVAILABLE = "CAPITAL_POLICY_UNAVAILABLE"
    INVALID_RISK_GEOMETRY = "INVALID_RISK_GEOMETRY"
    ZERO_QUANTITY_UNDER_POLICY = "ZERO_QUANTITY_UNDER_POLICY"


#: The semantic family a persisted `NOT_SIZED` verdict may draw from —
#: mirrors `EntryActionabilityReasonCode`'s own family-separation
#: discipline (ID-7A.1). `UPSTREAM_NOT_ACTIONABLE`/`UNVALIDATED_DIRECTION`/
#: `UPSTREAM_NOT_CURRENT` mean sizing arithmetic was never attempted at
#: all (policy never inspected); `CAPITAL_POLICY_UNAVAILABLE`/
#: `INVALID_RISK_GEOMETRY` mean it could not proceed even though the
#: opportunity itself was eligible, current, and (for the latter) policy
#: was genuinely available.
NOT_SIZED_REASON_CODES = frozenset(
    {
        PositionSizingReasonCode.UPSTREAM_NOT_ACTIONABLE,
        PositionSizingReasonCode.UNVALIDATED_DIRECTION,
        PositionSizingReasonCode.UPSTREAM_NOT_CURRENT,
        PositionSizingReasonCode.CAPITAL_POLICY_UNAVAILABLE,
        PositionSizingReasonCode.INVALID_RISK_GEOMETRY,
    }
)

#: Reason codes reached only AFTER capital-policy availability has been
#: confirmed (i.e. a real `CapitalPolicy` genuinely participated in
#: reaching this verdict, even though no quantity was computed) — the
#: ONLY `NOT_SIZED` family member(s) for which `policy_version` must
#: still be populated (§2 of the Owner's correction: policy_version
#: reflects true evaluation participation, never blindly erased).
POLICY_PARTICIPATED_NOT_SIZED_REASON_CODES = frozenset(
    {PositionSizingReasonCode.INVALID_RISK_GEOMETRY}
)

#: The sole reason a `ZERO_QUANTITY_UNDER_POLICY` verdict may carry.
ZERO_QUANTITY_REASON_CODES = frozenset({PositionSizingReasonCode.ZERO_QUANTITY_UNDER_POLICY})


@unique
class BindingConstraint(str, Enum):
    """Which V0 candidate quantity achieved the final minimum. More than
    one member may co-bind (an exact tie) — `PositionSizing.binding_constraints`
    is a tuple, never collapsed to one arbitrarily-chosen winner."""

    RISK_BUDGET = "RISK_BUDGET"
    MAX_POSITION_VALUE = "MAX_POSITION_VALUE"
    THEORETICAL_CAPITAL = "THEORETICAL_CAPITAL"


@dataclass(frozen=True, slots=True)
class PositionSizing:
    """Immutable, point-in-time, advisory-only ID-9 V0 artifact.

    **Composite identity (corrected, 2026-09-07, §2 of the Owner's
    correction):** the entire upstream `EntryActionability` composite
    key, copied verbatim, plus this artifact's own
    `position_sizing_as_of`, `sizing_methodology_version`, AND
    `policy_version` — no surrogate id, mirroring `EntryActionability`'s
    own frozen identity model (ID-7A0/ADR-015), but extended one field
    further: two sizing assertions over the exact same upstream
    checkpoint under two different `CapitalPolicy` versions are
    genuinely different assertions (e.g. policy-v1 -> quantity 100 vs.
    policy-v2 -> quantity 50) and must never share an identity. See
    `identity_tuple()`. This does NOT mean a policy-value change bumps
    `sizing_methodology_version` — POLICY VERSION remains an
    independent dimension from SIZING METHODOLOGY VERSION (§3); it
    means the *artifact's* identity is the combination of both, made
    explicit rather than left implicit.

    Three independent presence rules govern the optional fields (never
    conflated, per the Owner's own explicit instruction to keep
    methodology result, currentness, policy availability, and
    direction-validation status separate):

    1. Upstream-echoed risk-geometry fields (`direction`,
       `entry_reference_price`, `operative_invalidation_level`,
       `per_share_risk`) are present whenever the upstream
       `EntryActionability` genuinely reached `ACTIONABLE` — i.e.
       whenever `PositionSizingReasonCode.UPSTREAM_NOT_ACTIONABLE` is
       NOT in `reason_codes` — regardless of this artifact's own final
       `state` (e.g. a SHORT `ACTIONABLE` opportunity still echoes its
       real entry/invalidation/per-share-risk for explainability, even
       though it is refused sizing under `UNVALIDATED_DIRECTION`; a
       non-current `ACTIONABLE` opportunity under `UPSTREAM_NOT_CURRENT`
       does too).
    2. `policy_version` is present whenever a real `CapitalPolicy` was
       genuinely inspected while reaching this verdict — always true
       for `SIZED`/`ZERO_QUANTITY_UNDER_POLICY`, and additionally true
       for the narrow `NOT_SIZED`/`INVALID_RISK_GEOMETRY` case (reached
       only after policy availability was already confirmed) — never
       true for `UPSTREAM_NOT_ACTIONABLE`/`UNVALIDATED_DIRECTION`/
       `UPSTREAM_NOT_CURRENT`/`CAPITAL_POLICY_UNAVAILABLE` (policy was
       never inspected, or does not exist). See
       `POLICY_PARTICIPATED_NOT_SIZED_REASON_CODES`.
    3. The other capital-derived fields (`risk_budget_amount`,
       `max_position_value`, `theoretical_available_capital`,
       `risk_quantity`, `max_value_quantity`,
       `theoretical_capital_quantity`, `binding_constraints`) and result
       fields (`recommended_quantity`, `recommended_position_value`,
       `capital_at_risk`) are present if and only if
       `state in (SIZED, ZERO_QUANTITY_UNDER_POLICY)` — both states mean
       the full constraint computation genuinely ran; they differ only
       in whether the resulting minimum quantity is positive or floors
       to zero.
    """

    # ---- exact upstream EntryActionability identity, copied verbatim ----
    instrument_id: str
    session_date: date
    entry_qualification_as_of: datetime
    decision_id: str
    entry_qualification_methodology_version: str
    entry_actionability_as_of: datetime
    entry_actionability_methodology_version: str

    # ---- this artifact's own identity ----
    position_sizing_as_of: datetime
    sizing_methodology_version: str

    # ---- dimension (A): persisted-shape methodology verdict ----
    state: PositionSizingState
    reason_codes: tuple[PositionSizingReasonCode, ...]

    # ---- upstream-echoed risk geometry (rule 1) ----
    direction: Direction | None
    entry_reference_price: Decimal | None
    operative_invalidation_level: Decimal | None
    per_share_risk: Decimal | None

    # ---- capital-derived amounts (rule 2) ----
    policy_version: str | None
    risk_budget_amount: Decimal | None
    max_position_value: Decimal | None
    theoretical_available_capital: Decimal | None

    # ---- candidate quantities, one per V0 constraint (rule 2) ----
    risk_quantity: Decimal | None
    max_value_quantity: Decimal | None
    theoretical_capital_quantity: Decimal | None

    # ---- result (rule 2) ----
    recommended_quantity: Decimal | None
    recommended_position_value: Decimal | None
    capital_at_risk: Decimal | None
    binding_constraints: tuple[BindingConstraint, ...]

    # ---- market-time evidence checkpoint, echoed from the bound
    # EntryActionability exactly (independently optional — present
    # whenever the upstream artifact itself carried one, regardless of
    # this artifact's own state) ----
    evidence_as_of: datetime | None

    # ---- wall-clock evaluation instant (diagnostic only — never
    # identity, never a substitute for evidence_as_of) ----
    evaluated_at: datetime

    explanation: str

    def __post_init__(self) -> None:
        for name in (
            "instrument_id", "decision_id",
            "entry_qualification_methodology_version",
            "entry_actionability_methodology_version",
            "sizing_methodology_version",
        ):
            if not getattr(self, name):
                raise ValueError(f"PositionSizing.{name} is mandatory")
        for name in (
            "entry_qualification_as_of", "entry_actionability_as_of",
            "position_sizing_as_of", "evaluated_at",
        ):
            value: datetime = getattr(self, name)
            if value.tzinfo is None:
                raise ValueError(f"PositionSizing.{name} must be timezone-aware")
        if self.evidence_as_of is not None and self.evidence_as_of.tzinfo is None:
            raise ValueError("PositionSizing.evidence_as_of must be timezone-aware")

        if len(set(self.reason_codes)) != len(self.reason_codes):
            raise ValueError("PositionSizing.reason_codes must not contain duplicates")
        if not self.explanation:
            raise ValueError("PositionSizing.explanation is mandatory (ADR-005)")

        upstream_not_actionable = (
            PositionSizingReasonCode.UPSTREAM_NOT_ACTIONABLE in self.reason_codes
        )
        upstream_fields = (
            self.direction, self.entry_reference_price,
            self.operative_invalidation_level, self.per_share_risk,
        )
        if upstream_not_actionable:
            if any(f is not None for f in upstream_fields):
                raise ValueError(
                    "PositionSizing upstream-echoed risk-geometry fields must be None "
                    "when reason_codes includes UPSTREAM_NOT_ACTIONABLE"
                )
        else:
            if any(f is None for f in upstream_fields):
                raise ValueError(
                    "PositionSizing upstream-echoed risk-geometry fields "
                    "(direction, entry_reference_price, operative_invalidation_level, "
                    "per_share_risk) are mandatory whenever the upstream "
                    "EntryActionability reached ACTIONABLE"
                )
            if self.direction not in (Direction.LONG, Direction.SHORT):
                raise ValueError(
                    "PositionSizing.direction must be LONG or SHORT whenever the "
                    f"upstream EntryActionability reached ACTIONABLE, got {self.direction}"
                )

        # `policy_version` is tracked separately from the other six
        # capital-derived fields (§2 of the Owner's correction, 2026-09-07):
        # it must reflect true evaluation participation even for certain
        # NOT_SIZED verdicts (INVALID_RISK_GEOMETRY, reached only after a
        # real CapitalPolicy was confirmed available), whereas the other
        # six (budget amounts/quantities) are never populated unless the
        # full sizing computation genuinely ran (SIZED/ZERO_QUANTITY_UNDER_POLICY).
        capital_amount_fields = (
            self.risk_budget_amount, self.max_position_value,
            self.theoretical_available_capital, self.risk_quantity,
            self.max_value_quantity, self.theoretical_capital_quantity,
        )
        result_fields = (
            self.recommended_quantity, self.recommended_position_value, self.capital_at_risk,
        )

        if self.state is PositionSizingState.NOT_SIZED:
            if not self.reason_codes:
                raise ValueError("PositionSizing.reason_codes is mandatory when state=NOT_SIZED")
            foreign = set(self.reason_codes) - NOT_SIZED_REASON_CODES
            if foreign:
                raise ValueError(
                    "NOT_SIZED reason_codes must be drawn only from "
                    f"{sorted(c.value for c in NOT_SIZED_REASON_CODES)}, "
                    f"got {sorted(c.value for c in foreign)}"
                )
            if any(f is not None for f in capital_amount_fields) or any(f is not None for f in result_fields):
                raise ValueError(
                    "PositionSizing capital-amount/result fields must be None when state=NOT_SIZED"
                )
            if self.binding_constraints:
                raise ValueError("PositionSizing.binding_constraints must be empty when state=NOT_SIZED")

            policy_participated = bool(
                set(self.reason_codes) & POLICY_PARTICIPATED_NOT_SIZED_REASON_CODES
            )
            if policy_participated:
                if not self.policy_version:
                    raise ValueError(
                        "PositionSizing.policy_version is mandatory when reason_codes "
                        f"includes any of {sorted(c.value for c in POLICY_PARTICIPATED_NOT_SIZED_REASON_CODES)} "
                        "(a real CapitalPolicy was confirmed available before this verdict)"
                    )
            elif self.policy_version is not None:
                raise ValueError(
                    "PositionSizing.policy_version must be None when state=NOT_SIZED and "
                    "no policy-participated reason code is present (policy was never "
                    "inspected for this verdict) — got "
                    f"{self.policy_version!r} with reason_codes={[c.value for c in self.reason_codes]}"
                )
        else:
            # SIZED or ZERO_QUANTITY_UNDER_POLICY: the full constraint
            # computation genuinely ran -- every capital-derived/result
            # field (including policy_version) must be present.
            if (
                self.policy_version is None
                or any(f is None for f in capital_amount_fields)
                or any(f is None for f in result_fields)
            ):
                raise ValueError(
                    "PositionSizing policy_version/capital-amount/result fields are all "
                    f"mandatory when state={self.state.value}"
                )
            if not self.binding_constraints:
                raise ValueError(
                    f"PositionSizing.binding_constraints is mandatory when state={self.state.value}"
                )
            assert self.recommended_quantity is not None  # narrows for mypy/readers
            assert self.capital_at_risk is not None
            assert self.recommended_position_value is not None
            assert self.risk_budget_amount is not None
            assert self.max_position_value is not None
            assert self.theoretical_available_capital is not None
            if self.capital_at_risk > self.risk_budget_amount:
                raise ValueError(
                    "PositionSizing.capital_at_risk must not exceed risk_budget_amount "
                    f"({self.capital_at_risk} > {self.risk_budget_amount})"
                )
            if self.recommended_position_value > self.max_position_value:
                raise ValueError(
                    "PositionSizing.recommended_position_value must not exceed "
                    f"max_position_value ({self.recommended_position_value} > "
                    f"{self.max_position_value})"
                )
            if self.recommended_position_value > self.theoretical_available_capital:
                raise ValueError(
                    "PositionSizing.recommended_position_value must not exceed "
                    f"theoretical_available_capital ({self.recommended_position_value} > "
                    f"{self.theoretical_available_capital})"
                )

            if self.state is PositionSizingState.SIZED:
                if self.reason_codes:
                    raise ValueError(
                        "SIZED requires reason_codes to be empty — every persisted reason "
                        "code represents a blocker, and SIZED is not blocked"
                    )
                if self.recommended_quantity <= 0:
                    raise ValueError(
                        f"SIZED requires recommended_quantity > 0, got {self.recommended_quantity}"
                    )
            else:
                assert self.state is PositionSizingState.ZERO_QUANTITY_UNDER_POLICY
                if set(self.reason_codes) != ZERO_QUANTITY_REASON_CODES:
                    raise ValueError(
                        "ZERO_QUANTITY_UNDER_POLICY requires reason_codes == "
                        f"{sorted(c.value for c in ZERO_QUANTITY_REASON_CODES)}, "
                        f"got {sorted(c.value for c in self.reason_codes)}"
                    )
                if self.recommended_quantity != 0:
                    raise ValueError(
                        "ZERO_QUANTITY_UNDER_POLICY requires recommended_quantity == 0, "
                        f"got {self.recommended_quantity}"
                    )

    def identity_tuple(self) -> tuple[object, ...]:
        """The full composite identity of this sizing assertion (Owner
        correction, 2026-09-07, §2): the entire upstream `EntryActionability`
        identity, this artifact's own `position_sizing_as_of` and
        `sizing_methodology_version`, AND its `policy_version`.

        Two evaluations over the EXACT SAME upstream `EntryActionability`
        checkpoint and the SAME sizing methodology, but under two
        different `CapitalPolicy` versions, are genuinely different
        sizing assertions (e.g. policy-v1 -> quantity 100 vs. policy-v2
        -> quantity 50) — they must never compare as the same identity.
        This does NOT mean a policy-value change bumps
        `sizing_methodology_version` (that field identifies the
        MATHEMATICS only, frozen independently of policy, per §3 of the
        domain contract) — it means the ARTIFACT's own identity is the
        combination of both, mirrored here explicitly rather than left
        implicit in dataclass `__eq__`. No surrogate id is introduced;
        this is a derived view over already-stored fields, exactly like
        `entry_actionability_currentness.bound_entry_qualification_identity`
        is a derived view over `EntryActionability`'s own fields."""
        return (
            self.instrument_id, self.session_date, self.entry_qualification_as_of,
            self.decision_id, self.entry_qualification_methodology_version,
            self.entry_actionability_as_of, self.position_sizing_as_of,
            self.sizing_methodology_version, self.policy_version,
        )
