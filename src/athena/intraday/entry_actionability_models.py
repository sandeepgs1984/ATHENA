"""Entry Actionability domain contracts (ID-7A).

Implements the artifact ADR-015 froze and ID-7B/ID-7B.1/ID-7B.2/ID-7B.2.1
calibrated: an immutable, point-in-time, advisory-only record answering
WHEN/entry/risk for an already-`TRADE`-decided, already-`QUALIFIED`
opportunity — one layer downstream of `EntryQualification` (ADR-013's
layer 3, WHEN vs. EQ's layer-2 WHETHER). This module is domain contracts
and frozen V0 methodology *constants* only: no evaluator
(`EntryActionabilityEngine` does not exist — that is ID-7C), no
workflow wiring (ID-7E), no persistence engine beyond the plain
dataclasses here (schema/repository live in `data/store/`).

Three independent dimensions, frozen by ADR-015/ID-7A0.1 and preserved
exactly here:

(A) Persisted methodology state (`EntryActionabilityState`) — a
    point-in-time, immutable, evaluation-time-only verdict. Never
    mutated once written.
(B) Read-time currentness — NOT represented in this module at all.
    `is_currently_usable(...)`-style evaluation is a derived, non-
    persisted concept (ID-7A0.1) that ID-7A's persistence layer must
    never bake into a column; the currentness value objects/helper live
    separately (see `entry_actionability_currentness.py`) precisely so
    this module cannot accidentally reintroduce a persisted
    `is_current`/`STALE`/`EXPIRED` field.
(C) Evidence finality/provenance — inherited unchanged from the bound
    `EntryQualification`'s own `EntryEvidenceFinality` (reused directly,
    not duplicated — ID-7A's own authorization, ADR-015 §Decision).

V0 methodology frozen by ID-7B.2/ID-7B.2.1 (`docs/research/ID-7B2-ENTRY-RISK-CALIBRATION-VALIDATION.md`
§14, as corrected by that document's own §29):

- Entry trigger = the completed M5-close checkpoint price (never VWAP).
- Entry-location context = session VWAP + `deviation_pct`
  (informational only — `EXTENSION_GATE_NOT_SUPPORTED`, no exclusion
  gate, no calibrated zone width).
- Operative invalidation = VWAP-loss (independent of the M5-close entry
  trigger — non-degenerate). OR15-boundary (`COMPLETE`-only) is an
  always-optional, purely contextual secondary reference, never a
  fallback substituted for VWAP-loss.
- Reward = T1 (~+1%) / T2 (~+1.5%) goal bands (`GOAL_BANDS_ONLY`); RR is
  informational only (`RR_INFORMATIONAL_ONLY`), never a gate.
- No D1 ATR anywhere in this artifact (`NO_VALIDATED_FALLBACK` — nothing
  in V0 consumes it).
- Direction: the domain model remains fully bidirectional (`Direction`,
  reused from `Decision`) — V0's own empirical validation status is
  `LONG_VALIDATED_SHORT_UNVALIDATED` (a methodology-evidence fact, not a
  domain-representation constraint); nothing here hard-codes LONG-only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum, unique

from athena.domain.enums import DecisionType, Direction
from athena.intraday.entry_qualification_models import (
    EntryEvidenceFinality,
    EntryQualificationState,
)

#: ID-7A-minted V0 methodology version — deliberately namespaced apart
#: from `EntryQualification`'s own `DEFAULT_METHODOLOGY_VERSION`
#: ("entry-qualification-v0"), following the exact same naming
#: convention. Immutable once any production row exists.
DEFAULT_METHODOLOGY_VERSION = "entry-actionability-v0"

#: ID-7B.2 (discovery-fold-calibrated) / ID-7B.2.1 (contract-corrected):
#: T1/T2 are goal *bands*, not guaranteed or resistance-derived targets
#: (`GOAL_BANDS_ONLY`) — never a profitability claim.
T1_GOAL_BAND_PCT = Decimal("0.01")
T2_GOAL_BAND_PCT = Decimal("0.015")

#: ID-7B.2's validated freshness/currentness band: 2 completed M5
#: intervals (confirmed via `session/engine.py`'s own `_TIMEFRAME_MINUTES`
#: to be literally 10 minutes, not an approximation). ID-7B.2.1 corrected
#: this predicate to apply against `evidence_as_of`, never
#: `entry_actionability_as_of`/`evaluated_at`/`persisted_at` — see
#: `entry_actionability_currentness.py`. A frozen Python constant, not
#: operational config: per the ID-7A authorization, this value must not
#: become casually mutable configuration, since changing it would change
#: methodology identity without a version bump — mirrors the existing
#: `MAX_CHECKPOINT_OBSERVATION_DELAY_SECONDS` precedent
#: (`explosive_move/live/checkpoint_reference_price.py`).
CURRENTNESS_MAX_EVIDENCE_AGE_SECONDS = 600.0


@unique
class EntryActionabilityState(str, Enum):
    """Persisted, point-in-time, evaluation-time-only methodology verdict
    (dimension A). Deliberately three values only — no `EXPIRED`,
    `STALE`, `CURRENT`, or `SUPERSEDED` member exists here; those are
    read-time currentness concepts (dimension B, ID-7A0.1's own
    correction) and must never be persisted as methodology state.
    """

    UNKNOWN = "UNKNOWN"
    NOT_ACTIONABLE = "NOT_ACTIONABLE"
    ACTIONABLE = "ACTIONABLE"


@unique
class EntryActionabilityReasonCode(str, Enum):
    """Persisted, evaluation-time methodology reason vocabulary — frozen
    by ID-7B.2/ID-7B.2.1. Exactly four members; no
    `ENTRY_TOO_EXTENDED` (the extension gate was not adopted —
    `EXTENSION_GATE_NOT_SUPPORTED`) and no `SESSION_NOT_ACTIONABLE`
    (session ineligibility at evaluation time is already fully carried
    by `UPSTREAM_EQ_NOT_QUALIFIED`, since the bound EQ itself cannot be
    `QUALIFIED` outside `REGULAR`). Read-time currentness labels
    (`STALE`/`SUPERSEDED`/`SESSION_CLOSED`) are a wholly separate,
    non-persisted vocabulary — see `entry_actionability_currentness.py`.
    """

    UPSTREAM_DECISION_NOT_TRADE = "UPSTREAM_DECISION_NOT_TRADE"
    UPSTREAM_EQ_NOT_QUALIFIED = "UPSTREAM_EQ_NOT_QUALIFIED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    INVALIDATION_UNAVAILABLE = "INVALIDATION_UNAVAILABLE"


@unique
class EntryReferenceBasis(str, Enum):
    """What the entry trigger/reference price actually is. V0 has exactly
    one basis — the completed M5-close checkpoint price, never VWAP
    (ID-7B.2.1's own correction of an earlier degenerate contract)."""

    QUALIFYING_M5_CLOSE = "QUALIFYING_M5_CLOSE"


@dataclass(frozen=True, slots=True)
class EntryReference:
    """The V0 entry trigger — a single point reference, never a
    "trigger + zone" (`EXTENSION_GATE_NOT_SUPPORTED`, ID-7B.2 §7/§14: no
    calibrated zone width exists; fabricating one would misrepresent
    what was actually validated)."""

    price: Decimal
    basis: EntryReferenceBasis

    def __post_init__(self) -> None:
        if self.price <= 0:
            raise ValueError("EntryReference.price must be positive")


@dataclass(frozen=True, slots=True)
class EntryLocationContext:
    """Informational, non-gating entry-location evidence — the exact
    dimension ID-7B.2 §7 tested and found `EXTENSION_GATE_NOT_SUPPORTED`
    for. Never re-used as an invalidation reference against itself
    (would be degenerate, ID-7B.2 §8's own invariant)."""

    vwap: Decimal
    vwap_deviation_pct: Decimal

    def __post_init__(self) -> None:
        if self.vwap <= 0:
            raise ValueError("EntryLocationContext.vwap must be positive")


@unique
class InvalidationBasis(str, Enum):
    """V0's sole operative invalidation basis. No D1-ATR member exists
    (`NO_VALIDATED_FALLBACK`, ID-7B.2 §8/§18 — not part of V0 at all)."""

    VWAP_LOSS = "VWAP_LOSS"


@dataclass(frozen=True, slots=True)
class OperativeInvalidation:
    """The single level that determines risk distance and RR. Always
    paired against the M5-close `EntryReference`, never against a
    VWAP-derived entry anchor (would be the exact degenerate pairing
    ID-7B.2 §8 forbids and §29/ID-7B.2.1 corrected out of the contract).
    """

    level: Decimal
    basis: InvalidationBasis

    def __post_init__(self) -> None:
        if self.level <= 0:
            raise ValueError("OperativeInvalidation.level must be positive")


@unique
class OpeningRangeContextBasis(str, Enum):
    """V0's sole optional, purely contextual secondary invalidation
    reference basis."""

    OR15_BOUNDARY = "OR15_BOUNDARY"


@dataclass(frozen=True, slots=True)
class OpeningRangeContextReference:
    """Always-optional, purely contextual structural reference — never
    gating (its absence never forces `UNKNOWN`), never a fallback
    substituted for `OperativeInvalidation` when VWAP-loss is
    unavailable (no such substitution was calibrated or validated,
    ID-7B.2 §14), and never consumed by V0's own reward/risk
    calculation. Present only when the bound OR15
    `formation.status == COMPLETE` at the checkpoint."""

    level: Decimal
    basis: OpeningRangeContextBasis

    def __post_init__(self) -> None:
        if self.level <= 0:
            raise ValueError("OpeningRangeContextReference.level must be positive")


@unique
class RewardBasis(str, Enum):
    """V0's sole reward representation — percentage-based goal bands,
    never a guaranteed or structurally-validated target
    (`GOAL_BANDS_ONLY`, `V0_DOES_NOT_REQUIRE_GENERIC_SR`)."""

    GOAL_BANDS_ONLY = "GOAL_BANDS_ONLY"


@dataclass(frozen=True, slots=True)
class RewardReference:
    """T1/T2 goal-band prices (direction-aware, already resolved to an
    absolute price from the entry reference and the frozen
    `T1_GOAL_BAND_PCT`/`T2_GOAL_BAND_PCT` constants) plus informational-
    only reward/risk ratios (`RR_INFORMATIONAL_ONLY`, ID-7B.2 §10/§14 —
    never a gate; `None` only if risk distance could not be computed,
    which V0's own structural risk-geometry invariant makes unreachable
    whenever this object exists at all — see `EntryActionability.__post_init__`).
    """

    t1_price: Decimal
    t2_price: Decimal
    basis: RewardBasis
    reward_risk_to_t1: Decimal | None
    reward_risk_to_t2: Decimal | None

    def __post_init__(self) -> None:
        if self.t1_price <= 0 or self.t2_price <= 0:
            raise ValueError("RewardReference prices must be positive")


@dataclass(frozen=True, slots=True)
class EntryActionability:
    """Immutable, point-in-time, advisory-only ID-7 V0 artifact.

    Identity = the entire upstream `EntryQualification` composite key,
    copied verbatim (`instrument_id, session_date,
    entry_qualification_as_of, decision_id,
    entry_qualification_methodology_version` — ADR-015/ID-7A0.1's own
    frozen identity model), plus this artifact's own
    `entry_actionability_as_of` and `entry_actionability_methodology_version`.
    No surrogate id — `EntryQualification` itself has none, and
    inventing one here without architectural need was explicitly
    forbidden (ID-7A0 §Decision).

    `decision_type`/`run_id`/`cycle_id` and the bound EQ's own `state`
    are carried explicitly (denormalized), mirroring
    `EntryQualification`'s own established precedent for the identical
    auditability/explainability reason (never inferred by a caller from
    `decision_id`/EQ-identity alone).

    Value objects (`entry_reference`, `entry_location_context`,
    `operative_invalidation`, `reward`) are present if and only if
    `state == ACTIONABLE` — `NOT_ACTIONABLE`/`UNKNOWN` rows carry none of
    them, only `reason_codes` explaining why. `opening_range_context` is
    independently optional in all states (purely contextual, never
    gating).
    """

    # ---- exact upstream EntryQualification identity, copied verbatim ----
    instrument_id: str
    session_date: date
    entry_qualification_as_of: datetime
    decision_id: str
    entry_qualification_methodology_version: str

    # ---- this artifact's own identity ----
    entry_actionability_as_of: datetime
    entry_actionability_methodology_version: str

    # ---- denormalized upstream context (EQ's own precedent) ----
    decision_type: DecisionType
    direction: Direction
    entry_qualification_state: EntryQualificationState
    run_id: str
    cycle_id: str

    # ---- dimension (A): persisted methodology verdict ----
    state: EntryActionabilityState
    reason_codes: tuple[EntryActionabilityReasonCode, ...]

    # ---- dimension (C): evidence finality, inherited from bound EQ ----
    evidence_finality: EntryEvidenceFinality

    # ---- market-time evidence checkpoint (distinct from as_of above —
    # ADR-015/ID-7A0.1/ID-7B.2.1's own frozen distinction) ----
    evidence_as_of: datetime | None

    # ---- V0 value objects, present iff state == ACTIONABLE ----
    entry_reference: EntryReference | None
    entry_location_context: EntryLocationContext | None
    operative_invalidation: OperativeInvalidation | None
    reward: RewardReference | None

    # ---- always-independently-optional contextual reference ----
    opening_range_context: OpeningRangeContextReference | None

    # ---- wall-clock evaluation instant (diagnostic only — never
    # identity, never a substitute for evidence_as_of) ----
    evaluated_at: datetime

    explanation: str

    def __post_init__(self) -> None:
        for name in (
            "instrument_id", "decision_id",
            "entry_qualification_methodology_version",
            "entry_actionability_methodology_version",
            "run_id", "cycle_id",
        ):
            if not getattr(self, name):
                raise ValueError(f"EntryActionability.{name} is mandatory")
        for name in ("entry_qualification_as_of", "entry_actionability_as_of", "evaluated_at"):
            value: datetime = getattr(self, name)
            if value.tzinfo is None:
                raise ValueError(f"EntryActionability.{name} must be timezone-aware")
        if self.evidence_as_of is not None and self.evidence_as_of.tzinfo is None:
            raise ValueError("EntryActionability.evidence_as_of must be timezone-aware")
        if len(set(self.reason_codes)) != len(self.reason_codes):
            raise ValueError("EntryActionability.reason_codes must not contain duplicates")
        if not self.explanation:
            raise ValueError("EntryActionability.explanation is mandatory (ADR-005)")

        if self.state is EntryActionabilityState.ACTIONABLE:
            if not self.reason_codes:
                pass  # ACTIONABLE may legitimately have zero blocking reasons.
            if self.evidence_as_of is None:
                raise ValueError("ACTIONABLE requires evidence_as_of")
            if (
                self.entry_reference is None
                or self.entry_location_context is None
                or self.operative_invalidation is None
                or self.reward is None
            ):
                raise ValueError(
                    "ACTIONABLE requires entry_reference, entry_location_context, "
                    "operative_invalidation, and reward"
                )
            self._validate_risk_geometry()
        else:
            if not self.reason_codes:
                raise ValueError(
                    f"EntryActionability.reason_codes is mandatory when state={self.state.value}"
                )
            if (
                self.entry_reference is not None
                or self.entry_location_context is not None
                or self.operative_invalidation is not None
                or self.reward is not None
            ):
                raise ValueError(
                    f"EntryActionability value objects must be None when state={self.state.value}"
                )

    def _validate_risk_geometry(self) -> None:
        """Structural (never calibrated) risk-geometry invariant, per
        ID-7A's authorization item 14: reject zero risk distance and
        wrong-side geometry for the declared direction. Not a minimum-
        distance threshold — any positive, direction-valid distance is
        accepted; V0 calibrated no minimum."""
        entry = self.entry_reference
        invalidation = self.operative_invalidation
        assert entry is not None and invalidation is not None  # enforced above
        if self.direction is Direction.LONG:
            if invalidation.level >= entry.price:
                raise ValueError(
                    "LONG risk geometry invalid: operative_invalidation.level "
                    f"({invalidation.level}) must be strictly below "
                    f"entry_reference.price ({entry.price})"
                )
        elif self.direction is Direction.SHORT:
            if invalidation.level <= entry.price:
                raise ValueError(
                    "SHORT risk geometry invalid: operative_invalidation.level "
                    f"({invalidation.level}) must be strictly above "
                    f"entry_reference.price ({entry.price})"
                )
        else:
            raise ValueError(
                f"ACTIONABLE requires a directional Decision (LONG or SHORT), got {self.direction.value}"
            )
