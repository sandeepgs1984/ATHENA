"""Entry Qualification pure engine (ID-6B.2).

Implements — and implements ONLY — the v0 candidate-readiness methodology
the owner froze in ID-6B.1B (`docs/research/ID-6B.1B-QUALITY-ADJUSTED-POLICY-BASELINE.md`):

    VWAP readiness positive
    AND aggregate intraday trend == BULLISH
    AND (Relative Strength support OR Relative Volume support)

No new threshold is invented anywhere in this module — every condition
reads an existing categorical artifact (`VwapRelation`, `IntradayTrendLabel`,
`RelativeStrengthRelation`, `RelativeVolumeRelation`) exactly as ID-6B.1's
own harness already did. Aggregate `BULLISH` already means both the M5 and
M15 trend legs independently agree (`IntradayAnalyticsEngine._aggregate_trend`,
audited at source level in ID-6B.1B) — this engine deliberately consumes
only the aggregate label, never re-scores M5/M15 separately.

This is a PURE engine per ADR-013/ID-6A: deterministic, side-effect-free,
repository/provider/database/wall-clock/workflow independent. Every input
is explicit; the same immutable inputs always produce the exact same
output. No persistence, no workflow wiring, no API/UI (ID-6C/ID-6D own
those). No confirmation methodology runs in v0 — every emitted
`EntryQualification.confirmation` is `NOT_EVALUATED`
(`CONFIRMED_BY_POLICY` is never emitted here). `DISQUALIFIED_FOR_SESSION`
is never emitted by this engine.

Owner-ratified Option C (artifact-owned availability, ID-6B.1A/1B): the
engine never reads `SessionContext.data_quality` or
`IntradaySignalSet.data_quality` as a blanket readiness gate. Each of the
three named v0 conditions owns its own availability via its own
categorical artifact; `SessionDataQualityStatus.EXPECTED_BAR_MISSING`
alone never forces `UNKNOWN`/`NOT_YET` if all three consumed artifacts are
independently resolvable.

Every `EntryQualification` this engine produces is a point-in-time
evaluation (ID-6B.1B found ~40% checkpoint-level flicker in the
underlying rule): the engine never reads a prior `EntryQualification`,
never caches, and never performs hysteresis/debounce/confirmation.

Evidence finality (ADR-013's second orthogonal dimension) cannot be
determined from a `Decision` alone with the evidence available today — see
ID-6B.1B §20 and ADR-013's "Current Decision provenance ... remains
insufficient." This engine therefore does not attempt to infer it: the
caller supplies `evidence_finality` explicitly, and the engine only carries
it through unchanged, orthogonally to `state`, exactly as ADR-013 requires.
A future ID-6C/ID-6D milestone owns actually resolving that value from real
provenance data.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from athena.domain.decision import Decision
from athena.domain.enums import DecisionType
from athena.intraday.entry_qualification_models import (
    EntryEvidenceFinality,
    EntryQualification,
    EntryQualificationConfirmation,
    EntryQualificationEvidenceKind,
    EntryQualificationEvidenceRef,
    EntryQualificationReasonCode,
    EntryQualificationState,
)
from athena.intraday.models import IntradaySignalSet, IntradayTrendLabel, VwapRelation
from athena.intraday.relative_strength_models import RelativeStrengthRelation
from athena.intraday.relative_volume_models import RelativeVolumeRelation
from athena.session.models import SessionContext, SessionPhase

#: Identity of the frozen v0 methodology (ID-6B.1B). Not a tunable value —
#: this module has no numeric thresholds of its own to version.
DEFAULT_METHODOLOGY_VERSION = "entry-qualification-v0"

_ELIGIBLE_DECISION_TYPES = (DecisionType.WATCH, DecisionType.TRADE)


@dataclass(frozen=True, slots=True)
class EntryQualificationPolicy:
    """Immutable identity of the readiness methodology to apply.

    Deliberately carries no numeric thresholds: the v0 rule's own
    thresholds already belong to the upstream artifacts it reads
    (`VwapRelation`, `IntradayTrendLabel`, `RelativeStrengthRelation`,
    `RelativeVolumeRelation`), so this policy only freezes methodology
    identity/version and, if the caller has one, an upstream config
    snapshot provenance id — it does not claim ownership of thresholds
    that belong elsewhere.
    """

    methodology_version: str = DEFAULT_METHODOLOGY_VERSION
    config_snapshot_id: str | None = None

    def __post_init__(self) -> None:
        if not self.methodology_version:
            raise ValueError("EntryQualificationPolicy.methodology_version is mandatory")
        if self.config_snapshot_id is not None and not self.config_snapshot_id:
            raise ValueError("EntryQualificationPolicy.config_snapshot_id cannot be empty")


class _Tri(Enum):
    """Internal tri-state predicate value. Not exposed publicly — the
    published contract remains `EntryQualificationState`; this only helps
    the engine implement AND/OR without Python truthiness silently
    collapsing "unavailable" into "false" (owner §13)."""

    TRUE = "TRUE"
    FALSE = "FALSE"
    UNKNOWN = "UNKNOWN"


def _tri_and(*values: _Tri) -> _Tri:
    if any(v is _Tri.FALSE for v in values):
        return _Tri.FALSE
    if any(v is _Tri.UNKNOWN for v in values):
        return _Tri.UNKNOWN
    return _Tri.TRUE


def _tri_or(*values: _Tri) -> _Tri:
    if any(v is _Tri.TRUE for v in values):
        return _Tri.TRUE
    if any(v is _Tri.UNKNOWN for v in values):
        return _Tri.UNKNOWN
    return _Tri.FALSE


def _vwap_tri(signal_set: IntradaySignalSet) -> _Tri:
    relation = signal_set.vwap.relation
    if relation is VwapRelation.ABOVE_VWAP:
        return _Tri.TRUE
    if relation is VwapRelation.VWAP_UNAVAILABLE:
        return _Tri.UNKNOWN
    return _Tri.FALSE  # BELOW_VWAP or AT_VWAP: determinable, not positive.


def _trend_tri(signal_set: IntradaySignalSet) -> _Tri:
    label = signal_set.trend.trend_label
    if label is IntradayTrendLabel.BULLISH:
        return _Tri.TRUE
    if label is IntradayTrendLabel.UNKNOWN:
        return _Tri.UNKNOWN
    return _Tri.FALSE  # BEARISH or MIXED: determinable, not bullish.


def _rs_leg_tri(relation: RelativeStrengthRelation) -> _Tri:
    if relation is RelativeStrengthRelation.OUTPERFORMING:
        return _Tri.TRUE
    if relation is RelativeStrengthRelation.UNKNOWN:
        return _Tri.UNKNOWN
    return _Tri.FALSE  # UNDERPERFORMING or MATCHING.


def _rvol_tri(signal_set: IntradaySignalSet) -> _Tri:
    relation = signal_set.relative_volume.relation
    if relation is RelativeVolumeRelation.ABOVE_BASELINE:
        return _Tri.TRUE
    if relation is RelativeVolumeRelation.UNKNOWN:
        return _Tri.UNKNOWN
    return _Tri.FALSE  # BELOW_BASELINE or AT_BASELINE.


def _support_tri(signal_set: IntradaySignalSet) -> _Tri:
    """RS support OR RVOL support, each independently available or not.

    A genuine RS/RVOL OUTPERFORM/ABOVE_BASELINE dominates regardless of
    whether the other branch is unavailable (owner §11); the support
    condition is UNKNOWN only when neither branch can be determined."""
    rs = signal_set.relative_strength
    rs_tri = _tri_or(
        _rs_leg_tri(rs.stock_vs_market_relation),
        _rs_leg_tri(rs.stock_vs_sector_relation),
    )
    return _tri_or(rs_tri, _rvol_tri(signal_set))


_LEGS = ("vwap", "trend", "support")

_UNAVAILABLE_REASON = {
    "vwap": EntryQualificationReasonCode.VWAP_EVIDENCE_UNAVAILABLE,
    "trend": EntryQualificationReasonCode.TREND_EVIDENCE_UNAVAILABLE,
    "support": EntryQualificationReasonCode.SUPPORT_EVIDENCE_UNRESOLVED,
}
_NOT_MET_REASON = {
    "vwap": EntryQualificationReasonCode.VWAP_CONDITION_NOT_MET,
    "trend": EntryQualificationReasonCode.TREND_CONDITION_NOT_MET,
    "support": EntryQualificationReasonCode.SUPPORT_CONDITION_NOT_MET,
}
_MET_REASON = {
    "vwap": EntryQualificationReasonCode.VWAP_CONDITION_MET,
    "trend": EntryQualificationReasonCode.TREND_CONDITION_MET,
    "support": EntryQualificationReasonCode.SUPPORT_CONDITION_MET,
}
_MET_PHRASE = {
    "vwap": "positive VWAP",
    "trend": "bullish M5/M15 trend",
    "support": "RS/RVOL support",
}
_NOT_MET_PHRASE = {
    "vwap": "VWAP condition not met",
    "trend": "trend condition not met",
    "support": "RS/RVOL support condition not met",
}
_UNAVAILABLE_PHRASE = {
    "vwap": "VWAP evidence unavailable",
    "trend": "trend evidence unavailable",
    "support": "RS/RVOL support unresolved",
}


class EntryQualificationEngine:
    """Deterministic, side-effect-free v0 readiness evaluator.

    O(1) per candidate: no candle iteration, no repository access, no
    provider/network call, no history scan, no lookup of any prior
    `EntryQualification`. `evaluate()` is the only public method.
    """

    def evaluate(
        self,
        *,
        decision: Decision,
        session_context: SessionContext,
        signal_set: IntradaySignalSet,
        evidence_finality: EntryEvidenceFinality,
        policy: EntryQualificationPolicy | None = None,
    ) -> EntryQualification:
        policy = policy if policy is not None else EntryQualificationPolicy()
        instrument_id = _resolve_instrument_id(decision, session_context)

        if decision.decision_type not in _ELIGIBLE_DECISION_TYPES:
            return self._emit(
                decision,
                session_context,
                instrument_id,
                evidence_finality,
                policy,
                state=EntryQualificationState.OUT_OF_SCOPE,
                reason_codes=(EntryQualificationReasonCode.STRUCTURALLY_OUT_OF_SCOPE,),
                explanation=(
                    "OUT_OF_SCOPE: decision type "
                    f"{decision.decision_type.value} is not eligible for entry qualification."
                ),
                evidence_refs=_structural_evidence_refs(decision, session_context),
            )

        phase = session_context.phase

        if phase is SessionPhase.NOT_A_TRADING_SESSION:
            return self._emit(
                decision,
                session_context,
                instrument_id,
                evidence_finality,
                policy,
                state=EntryQualificationState.OUT_OF_SCOPE,
                reason_codes=(EntryQualificationReasonCode.STRUCTURALLY_OUT_OF_SCOPE,),
                explanation="OUT_OF_SCOPE: today is not a trading session.",
                evidence_refs=_structural_evidence_refs(decision, session_context),
            )

        if phase is SessionPhase.CLOSED:
            return self._emit(
                decision,
                session_context,
                instrument_id,
                evidence_finality,
                policy,
                state=EntryQualificationState.EXPIRED,
                reason_codes=(EntryQualificationReasonCode.SESSION_EXPIRED,),
                explanation="EXPIRED: trading session has closed.",
                evidence_refs=_structural_evidence_refs(decision, session_context),
            )

        if phase is SessionPhase.PRE_OPEN:
            return self._emit(
                decision,
                session_context,
                instrument_id,
                evidence_finality,
                policy,
                state=EntryQualificationState.NOT_YET,
                reason_codes=(EntryQualificationReasonCode.INSUFFICIENT_EVIDENCE,),
                explanation=(
                    "NOT_YET: session is pre-open; readiness evidence is not yet expected."
                ),
                evidence_refs=_structural_evidence_refs(decision, session_context),
            )

        # phase is SessionPhase.REGULAR: evaluate the frozen v0 expression.
        legs = {
            "vwap": _vwap_tri(signal_set),
            "trend": _trend_tri(signal_set),
            "support": _support_tri(signal_set),
        }
        overall = _tri_and(*(legs[leg] for leg in _LEGS))

        if overall is _Tri.TRUE:
            state = EntryQualificationState.QUALIFIED
            reason_codes = (
                *(_MET_REASON[leg] for leg in _LEGS),
                EntryQualificationReasonCode.V0_READINESS_POLICY_SATISFIED,
            )
            explanation = "QUALIFIED: " + ", ".join(_MET_PHRASE[leg] for leg in _LEGS) + "."
        elif overall is _Tri.FALSE:
            state = EntryQualificationState.NOT_YET
            failed = [leg for leg in _LEGS if legs[leg] is _Tri.FALSE]
            reason_codes = tuple(_NOT_MET_REASON[leg] for leg in failed)
            explanation = "NOT_YET: " + ", ".join(_NOT_MET_PHRASE[leg] for leg in failed) + "."
        else:
            state = EntryQualificationState.UNKNOWN
            unresolved = [leg for leg in _LEGS if legs[leg] is _Tri.UNKNOWN]
            reason_codes = tuple(_UNAVAILABLE_REASON[leg] for leg in unresolved)
            explanation = (
                "UNKNOWN: " + ", ".join(_UNAVAILABLE_PHRASE[leg] for leg in unresolved) + "."
            )

        return self._emit(
            decision,
            session_context,
            instrument_id,
            evidence_finality,
            policy,
            state=state,
            reason_codes=reason_codes,
            explanation=explanation,
            evidence_refs=_full_evidence_refs(decision, session_context, signal_set),
        )

    @staticmethod
    def _emit(
        decision: Decision,
        session_context: SessionContext,
        instrument_id: str,
        evidence_finality: EntryEvidenceFinality,
        policy: EntryQualificationPolicy,
        *,
        state: EntryQualificationState,
        reason_codes: tuple[EntryQualificationReasonCode, ...],
        explanation: str,
        evidence_refs: tuple[EntryQualificationEvidenceRef, ...],
    ) -> EntryQualification:
        return EntryQualification(
            instrument_id=instrument_id,
            session_date=session_context.session_date,
            as_of=session_context.as_of,
            run_id=decision.run_id,
            cycle_id=decision.cycle_id,
            decision_id=decision.decision_id,
            decision_type=decision.decision_type,
            state=state,
            evidence_finality=evidence_finality,
            confirmation=EntryQualificationConfirmation.NOT_EVALUATED,
            reason_codes=reason_codes,
            evidence_refs=evidence_refs,
            methodology_version=policy.methodology_version,
            config_snapshot_id=policy.config_snapshot_id,
            explanation=explanation,
        )


def _resolve_instrument_id(decision: Decision, session_context: SessionContext) -> str:
    if decision.instrument_id is None:
        return session_context.instrument_id
    if decision.instrument_id != session_context.instrument_id:
        raise ValueError(
            "EntryQualificationEngine received a Decision "
            f"({decision.instrument_id!r}) and SessionContext "
            f"({session_context.instrument_id!r}) for two different instruments"
        )
    return decision.instrument_id


def _structural_evidence_refs(
    decision: Decision, session_context: SessionContext
) -> tuple[EntryQualificationEvidenceRef, ...]:
    return (
        EntryQualificationEvidenceRef(
            kind=EntryQualificationEvidenceKind.DECISION,
            ref_id=decision.decision_id,
            as_of=decision.ts,
            explanation="Canonical Decision referenced for structural/lifecycle eligibility.",
        ),
        EntryQualificationEvidenceRef(
            kind=EntryQualificationEvidenceKind.SESSION_CONTEXT,
            ref_id=None,
            as_of=session_context.as_of,
            explanation="SessionContext referenced for structural/lifecycle eligibility.",
        ),
    )


def _full_evidence_refs(
    decision: Decision, session_context: SessionContext, signal_set: IntradaySignalSet
) -> tuple[EntryQualificationEvidenceRef, ...]:
    return (
        *_structural_evidence_refs(decision, session_context),
        EntryQualificationEvidenceRef(
            kind=EntryQualificationEvidenceKind.INTRADAY_SIGNAL_SET,
            ref_id=None,
            as_of=signal_set.as_of,
            explanation="IntradaySignalSet referenced for v0 readiness methodology evaluation.",
        ),
    )
