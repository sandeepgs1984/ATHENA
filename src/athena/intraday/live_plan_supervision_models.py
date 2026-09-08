"""Live Plan Supervision domain contracts (ID-10 V0).

Answers, for one already-`SIZED`-or-not-yet-sized-but-`ACTIONABLE`
opportunity: does this specific, already-persisted `EntryActionability`
still remain valid as the session evolves? One layer downstream of
`PositionSizing` (ID-9's own layer 4, HOW MUCH) — ID-10 is layer 5,
DOES IT STILL HOLD — mirroring the whole track's own frozen dimension
discipline (persisted upstream identity vs. read-time currentness vs.
supervision verdict vs. target-progress fact, never conflated) and the
established "reject an untruthful supplied combination" `__post_init__`
philosophy.

Frozen by the Owner's ID-10 V0 methodology-freeze authorization
(2026-09-08), following three correction rounds recorded in
`docs/research/ID-10-LIVE-PLAN-SUPERVISION-DISCOVERY.md`:

- Canonical supervision anchor: one exact, already-persisted
  `EntryActionability` row, identified by its own full composite key —
  never "whatever is currently latest", never `PositionSizing` (which
  cannot anchor identity since it is never persisted).
- V0 direction scope: LONG only — `LONG_VALIDATED_SHORT_UNVALIDATED`
  means SHORT (and the structurally-unreachable `NONE`) must never
  receive a supervision verdict; refused with `UNVALIDATED_DIRECTION`.
- Hard invalidation: the completed M5 close falls below (LONG) the
  **evolving, session-cumulative VWAP recomputed at that same
  checkpoint** — never the frozen `EntryActionability.operative_
  invalidation.level` (a synchronous entry-checkpoint snapshot, correct
  for ID-9's own sizing math, methodologically wrong as a forward
  invalidation line — see the discovery document's §7).
- Invalidation is **path-dependent**: once a qualifying VWAP-loss candle
  has occurred anywhere in the supervision event window (strictly after
  the supervised `EntryActionability`'s own `evidence_as_of`), the
  verdict remains `INVALIDATED` for every later evaluation of that same
  identity, even if a later candle recovers back above VWAP.
- Target progress (T1/T2 goal-band intrabar touch) is likewise
  path-dependent, over the identical event window, orthogonal to and
  never gating the supervision verdict — informational only.
- `WEAKENING` is explicitly DEFERRED — no dimension survives as a
  separate, deterministic, evidence-backed soft signal for V0.
- `PERSISTENCE_NOT_YET_REQUIRED` — every field here is reconstructed
  deterministically from (one persisted `EntryActionability` identity +
  fresh currentness + a freshly-composed bounded candle window) on every
  evaluation; no supervision history/FSM is stored anywhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum, unique

from athena.domain.enums import Direction
from athena.intraday.entry_actionability_currentness import CurrentnessResult

#: ID-10-minted V0 methodology version — namespaced apart from every
#: other artifact's own methodology version in this track (e.g.
#: `"position-sizing-v0"`), following the exact same convention.
#: Immutable once any production row/consumer exists.
DEFAULT_METHODOLOGY_VERSION = "live-plan-supervision-v0"


@unique
class LivePlanSupervisionState(str, Enum):
    """Persisted-shape-if-ever-persisted, evaluation-time-only
    methodology verdict — deliberately three values only, mirroring
    `PositionSizingState`'s/`EntryActionabilityState`'s own minimal
    discipline. No `WEAKENING` member — explicitly deferred (no
    dimension survived source review as a genuinely separate,
    deterministic, evidence-backed soft signal for V0)."""

    NOT_APPLICABLE = "NOT_APPLICABLE"
    VALID = "VALID"
    INVALIDATED = "INVALIDATED"


@unique
class LivePlanSupervisionReasonCode(str, Enum):
    """Reason vocabulary, family-separated exactly like
    `PositionSizingReasonCode`/`EntryActionabilityReasonCode` — a
    `NOT_APPLICABLE` verdict draws only from `NOT_APPLICABLE_REASON_CODES`;
    `INVALIDATED` draws only from `INVALIDATED_REASON_CODES`; `VALID`
    carries none."""

    UPSTREAM_NOT_ACTIONABLE = "UPSTREAM_NOT_ACTIONABLE"
    UNVALIDATED_DIRECTION = "UNVALIDATED_DIRECTION"
    UPSTREAM_NOT_CURRENT = "UPSTREAM_NOT_CURRENT"
    VWAP_LOSS = "VWAP_LOSS"


#: The semantic family a persisted `NOT_APPLICABLE` verdict may draw
#: from. All three mean supervision arithmetic was never (meaningfully)
#: attempted — currentness/direction/upstream-actionability was never
#: satisfied, so no candle-path evidence composition was performed
#: either (§13 of the discovery document: never compose evidence for a
#: row already rejected by an earlier deterministic gate).
NOT_APPLICABLE_REASON_CODES = frozenset(
    {
        LivePlanSupervisionReasonCode.UPSTREAM_NOT_ACTIONABLE,
        LivePlanSupervisionReasonCode.UNVALIDATED_DIRECTION,
        LivePlanSupervisionReasonCode.UPSTREAM_NOT_CURRENT,
    }
)

#: The sole reason an `INVALIDATED` verdict may carry.
INVALIDATED_REASON_CODES = frozenset({LivePlanSupervisionReasonCode.VWAP_LOSS})


@unique
class TargetProgress(str, Enum):
    """Orthogonal, informational-only target-reachability fact — never
    gates `LivePlanSupervisionState`, never becomes execution language.
    `T2_REACHED` logically subsumes `T1_REACHED` (T2 is the farther goal
    band; touching it structurally implies price also passed through T1)
    — the compact V0 state reports only the highest band reached, while
    `TargetProgressEvidence` below preserves both timestamps for
    provenance."""

    NONE_REACHED = "NONE_REACHED"
    T1_REACHED = "T1_REACHED"
    T2_REACHED = "T2_REACHED"


@dataclass(frozen=True, slots=True)
class VwapLossEvidence:
    """Immutable, path-dependent hard-invalidation fact, composed by the
    workflow stage (never the pure engine) from the bounded supervision
    event window, using session-cumulative VWAP recomputed at each
    candle's own completion instant (never the frozen
    `EntryActionability.operative_invalidation.level`).

    `triggered`/`first_triggered_as_of`/`trigger_close`/`trigger_vwap`
    describe the **historical** fact — once `triggered` is `True` for a
    given supervised `EntryActionability` identity, no later evaluation
    (which always re-walks the same historical candles, plus whichever
    new ones have since completed) can ever recompute it `False`: the
    chronologically-first trigger candle is still the chronologically-
    first trigger in any longer path that still contains it. This
    permanence is a property of the recomputation itself, not a stored
    flag.

    `current_close`/`current_vwap`/`currently_above_vwap` describe the
    **current-checkpoint** relation only — kept explicitly separate for
    presentation/explainability, and never a substitute for `triggered`
    when determining the supervision verdict.
    """

    triggered: bool
    first_triggered_as_of: datetime | None
    trigger_close: Decimal | None
    trigger_vwap: Decimal | None
    current_close: Decimal | None
    current_vwap: Decimal | None
    currently_above_vwap: bool | None

    def __post_init__(self) -> None:
        trigger_fields = (self.first_triggered_as_of, self.trigger_close, self.trigger_vwap)
        if self.triggered:
            if any(f is None for f in trigger_fields):
                raise ValueError(
                    "VwapLossEvidence.first_triggered_as_of/trigger_close/trigger_vwap "
                    "are all mandatory when triggered=True"
                )
        else:
            if any(f is not None for f in trigger_fields):
                raise ValueError(
                    "VwapLossEvidence.first_triggered_as_of/trigger_close/trigger_vwap "
                    "must all be None when triggered=False"
                )
        current_fields = (self.current_close, self.current_vwap)
        if any(f is None for f in current_fields) != all(f is None for f in current_fields):
            raise ValueError(
                "VwapLossEvidence.current_close and current_vwap must be present or "
                "absent together"
            )
        if self.currently_above_vwap is not None and self.current_close is None:
            raise ValueError(
                "VwapLossEvidence.currently_above_vwap requires current_close/current_vwap "
                "to be present"
            )
        if self.first_triggered_as_of is not None and self.first_triggered_as_of.tzinfo is None:
            raise ValueError("VwapLossEvidence.first_triggered_as_of must be timezone-aware")


@dataclass(frozen=True, slots=True)
class TargetProgressEvidence:
    """Immutable, path-dependent target-reachability fact, composed by
    the workflow stage from the identical bounded supervision event
    window `VwapLossEvidence` uses (no session-history prefix needed —
    target reachability only concerns candles after the plan began).
    Never gates `LivePlanSupervisionState`; never restores an
    invalidated plan; never implies a fill or that shares were sold."""

    status: TargetProgress
    t1_reached_as_of: datetime | None
    t2_reached_as_of: datetime | None

    def __post_init__(self) -> None:
        if self.status is TargetProgress.NONE_REACHED:
            if self.t1_reached_as_of is not None or self.t2_reached_as_of is not None:
                raise ValueError(
                    "TargetProgressEvidence.t1_reached_as_of/t2_reached_as_of must both be "
                    "None when status=NONE_REACHED"
                )
        elif self.status is TargetProgress.T1_REACHED:
            if self.t1_reached_as_of is None:
                raise ValueError(
                    "TargetProgressEvidence.t1_reached_as_of is mandatory when status=T1_REACHED"
                )
            if self.t2_reached_as_of is not None:
                raise ValueError(
                    "TargetProgressEvidence.t2_reached_as_of must be None when status=T1_REACHED "
                    "(T2 was not reached)"
                )
        else:
            assert self.status is TargetProgress.T2_REACHED
            if self.t1_reached_as_of is None or self.t2_reached_as_of is None:
                raise ValueError(
                    "TargetProgressEvidence.t1_reached_as_of and t2_reached_as_of are both "
                    "mandatory when status=T2_REACHED (T2 structurally implies T1)"
                )
            if self.t1_reached_as_of > self.t2_reached_as_of:
                raise ValueError(
                    "TargetProgressEvidence.t1_reached_as_of must be at or before "
                    "t2_reached_as_of"
                )
        for name in ("t1_reached_as_of", "t2_reached_as_of"):
            value: datetime | None = getattr(self, name)
            if value is not None and value.tzinfo is None:
                raise ValueError(f"TargetProgressEvidence.{name} must be timezone-aware")


@dataclass(frozen=True, slots=True)
class LivePlanSupervision:
    """Immutable, point-in-time, advisory-only ID-10 V0 artifact.

    **Identity**: the entire upstream `EntryActionability` composite key,
    copied verbatim, plus this artifact's own `supervision_as_of` and
    `supervision_methodology_version` — no surrogate id, mirroring every
    other artifact in this track. Deliberately does NOT include a policy
    or capital-derived field in its identity (unlike `PositionSizing`) —
    ID-10 has no policy-equivalent concept; the supervised
    `EntryActionability` identity plus the evaluation checkpoint fully
    determines the result, since it is a pure, deterministic recompute.

    **Three field-presence rules**, never conflated (mirrors
    `PositionSizing`'s own discipline exactly):

    1. Upstream-echoed risk-geometry fields (`direction`,
       `operative_invalidation_level`, `t1_price`, `t2_price`) are
       present whenever the upstream `EntryActionability` genuinely
       reached `ACTIONABLE` — i.e. whenever
       `LivePlanSupervisionReasonCode.UPSTREAM_NOT_ACTIONABLE` is NOT in
       `reason_codes` — regardless of this artifact's own final `state`
       (e.g. a SHORT `ACTIONABLE` opportunity still echoes its real
       operative invalidation/reward for explainability, even though it
       is refused supervision under `UNVALIDATED_DIRECTION`).
    2. `currentness` (the full `CurrentnessResult`, preserved for
       explainability) is present whenever `entry_actionability` was not
       `None` at the workflow level — i.e. always, for every genuinely
       evaluated row — since computing it is cheap and pure and the
       workflow stage always computes it before any gating.
    3. `vwap_loss_evidence`/`target_progress_evidence` are present if and
       only if `state in (VALID, INVALIDATED)` — both states mean the
       full bounded-path evidence composition genuinely ran; `NOT_APPLICABLE`
       means it deliberately never did (no wasted repository work for a
       row an earlier gate already rejected).
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
    supervision_as_of: datetime
    supervision_methodology_version: str

    # ---- dimension (A): supervision verdict ----
    state: LivePlanSupervisionState
    reason_codes: tuple[LivePlanSupervisionReasonCode, ...]

    # ---- dimension (B): currentness, reused verbatim (rule 2) ----
    currentness: CurrentnessResult

    # ---- upstream-echoed risk geometry (rule 1) ----
    direction: Direction | None
    operative_invalidation_level: Decimal | None
    t1_price: Decimal | None
    t2_price: Decimal | None

    # ---- dimension (C): path-dependent evidence (rule 3) ----
    vwap_loss_evidence: VwapLossEvidence | None
    target_progress_evidence: TargetProgressEvidence | None

    # ---- market-time evidence checkpoint, echoed from the bound
    # EntryActionability exactly (independently optional — present
    # whenever the upstream artifact itself carried one) ----
    evidence_as_of: datetime | None

    # ---- wall-clock evaluation instant (diagnostic only — never
    # identity beyond supervision_as_of, never a substitute for it) ----
    evaluated_at: datetime

    explanation: str

    def __post_init__(self) -> None:
        for name in (
            "instrument_id", "decision_id",
            "entry_qualification_methodology_version",
            "entry_actionability_methodology_version",
            "supervision_methodology_version",
        ):
            if not getattr(self, name):
                raise ValueError(f"LivePlanSupervision.{name} is mandatory")
        for name in (
            "entry_qualification_as_of", "entry_actionability_as_of",
            "supervision_as_of", "evaluated_at",
        ):
            value: datetime = getattr(self, name)
            if value.tzinfo is None:
                raise ValueError(f"LivePlanSupervision.{name} must be timezone-aware")
        if self.evidence_as_of is not None and self.evidence_as_of.tzinfo is None:
            raise ValueError("LivePlanSupervision.evidence_as_of must be timezone-aware")

        if len(set(self.reason_codes)) != len(self.reason_codes):
            raise ValueError("LivePlanSupervision.reason_codes must not contain duplicates")
        if not self.explanation:
            raise ValueError("LivePlanSupervision.explanation is mandatory (ADR-005)")

        upstream_not_actionable = (
            LivePlanSupervisionReasonCode.UPSTREAM_NOT_ACTIONABLE in self.reason_codes
        )
        upstream_fields = (
            self.direction, self.operative_invalidation_level, self.t1_price, self.t2_price,
        )
        if upstream_not_actionable:
            if any(f is not None for f in upstream_fields):
                raise ValueError(
                    "LivePlanSupervision upstream-echoed risk-geometry fields must be None "
                    "when reason_codes includes UPSTREAM_NOT_ACTIONABLE"
                )
        else:
            if any(f is None for f in upstream_fields):
                raise ValueError(
                    "LivePlanSupervision upstream-echoed risk-geometry fields (direction, "
                    "operative_invalidation_level, t1_price, t2_price) are mandatory whenever "
                    "the upstream EntryActionability reached ACTIONABLE"
                )

        if self.state is LivePlanSupervisionState.NOT_APPLICABLE:
            if not self.reason_codes:
                raise ValueError(
                    "LivePlanSupervision.reason_codes is mandatory when state=NOT_APPLICABLE"
                )
            foreign = set(self.reason_codes) - NOT_APPLICABLE_REASON_CODES
            if foreign:
                raise ValueError(
                    "NOT_APPLICABLE reason_codes must be drawn only from "
                    f"{sorted(c.value for c in NOT_APPLICABLE_REASON_CODES)}, "
                    f"got {sorted(c.value for c in foreign)}"
                )
            if self.vwap_loss_evidence is not None or self.target_progress_evidence is not None:
                raise ValueError(
                    "LivePlanSupervision.vwap_loss_evidence/target_progress_evidence must be "
                    "None when state=NOT_APPLICABLE"
                )
        else:
            if self.vwap_loss_evidence is None or self.target_progress_evidence is None:
                raise ValueError(
                    "LivePlanSupervision.vwap_loss_evidence/target_progress_evidence are both "
                    f"mandatory when state={self.state.value}"
                )
            if self.state is LivePlanSupervisionState.VALID:
                if self.reason_codes:
                    raise ValueError(
                        "VALID requires reason_codes to be empty — every persisted reason "
                        "code represents a blocker, and VALID is not blocked"
                    )
                if self.vwap_loss_evidence.triggered:
                    raise ValueError(
                        "LivePlanSupervision.state=VALID is inconsistent with "
                        "vwap_loss_evidence.triggered=True"
                    )
            else:
                assert self.state is LivePlanSupervisionState.INVALIDATED
                if set(self.reason_codes) != INVALIDATED_REASON_CODES:
                    raise ValueError(
                        "INVALIDATED requires reason_codes == "
                        f"{sorted(c.value for c in INVALIDATED_REASON_CODES)}, "
                        f"got {sorted(c.value for c in self.reason_codes)}"
                    )
                if not self.vwap_loss_evidence.triggered:
                    raise ValueError(
                        "LivePlanSupervision.state=INVALIDATED requires "
                        "vwap_loss_evidence.triggered=True"
                    )

    def identity_tuple(self) -> tuple[object, ...]:
        """The full composite identity of this supervision assertion —
        the entire upstream `EntryActionability` identity plus this
        artifact's own `supervision_as_of` and
        `supervision_methodology_version`. No surrogate id; a derived
        view over already-stored fields, exactly like
        `PositionSizing.identity_tuple()`/
        `entry_actionability_currentness.bound_entry_qualification_identity`."""
        return (
            self.instrument_id, self.session_date, self.entry_qualification_as_of,
            self.decision_id, self.entry_qualification_methodology_version,
            self.entry_actionability_as_of, self.supervision_as_of,
            self.supervision_methodology_version,
        )
