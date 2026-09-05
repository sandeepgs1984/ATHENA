"""Entry Actionability pure V0 deterministic evaluator (ID-7C).

Implements — and implements ONLY — the frozen V0 methodology ID-7B/
ID-7B.1/ID-7B.2/ID-7B.2.1 calibrated and ID-7A's domain model encodes:
given one exact canonical `Decision`, one exact bound `EntryQualification`,
and already-computed point-in-time layer-3 market evidence, what was the
`EntryActionability` methodology verdict at that checkpoint?

This is a PURE engine, mirroring `EntryQualificationEngine`'s own
established contract exactly (ID-6B.2): deterministic, side-effect-free,
repository/provider/database/wall-clock/workflow independent. Every input
is explicit; the same immutable inputs always produce the exact same
methodology content (only the injected `evaluated_at` diagnostic
timestamp may legitimately differ between two calls with otherwise
identical inputs). No persistence (`save_entry_actionability` lives on
`SqliteRepository`, ID-7A), no "latest Decision/EQ" resolution (that is a
caller/workflow responsibility, ID-7E), no currentness evaluation (that
is `entry_actionability_currentness.is_currently_usable`, ID-7A), no
`WorkflowStage` wiring (ID-7E), no provider/network call.

Evaluation-time session eligibility is never re-invented here: the bound
`EntryQualification` already carries session eligibility semantics (it
cannot be `QUALIFIED` outside `REGULAR`, ID-6B.1B) — if session made EQ
non-`QUALIFIED`, the result is `NOT_ACTIONABLE` + `UPSTREAM_EQ_NOT_QUALIFIED`,
never a separately invented `SESSION_NOT_ACTIONABLE` reason (ID-7B.2.1
already rejected that code).

Frozen evaluation structure (ID-7A.2's own domain-level invariant,
mirrored here at the point that actually produces it; the exact
evaluation ORDER below was itself corrected by ID-7C.2 — see that
section's own note):

    UPSTREAM ELIGIBILITY (Decision == TRADE AND exact EQ == QUALIFIED)
        -> then LAYER-3 EVIDENCE SUFFICIENCY (completed M5 close + VWAP)
            -> then RISK GEOMETRY (VWAP-loss vs. M5-close, direction-aware)
                -> ACTIONABLE

Evaluation-order boundary (ID-7C.2 — auditable for ID-7E): exact
Decision/EQ *binding* validation (`_validate_binding`) is global — it
runs unconditionally first, since a mismatched pair can never produce a
trustworthy verdict of any kind, eligible or not. Upstream methodology
gates are then computed and short-circuit IMMEDIATELY after that, before
any candidate/checkpoint-relative layer-3 evidence check. Only once
Decision == TRADE and the exact EQ == QUALIFIED does the evaluator begin
validating `market_evidence` against the resolved candidate/checkpoint
(candle instrument+completion, VWAP-provenance-vs-checkpoint, OR15
instrument/session/checkpoint coherence) — an upstream-ineligible
candidate's layer-3 evidence is never even inspected, so a malformed or
incoherent-but-otherwise-structurally-valid `market_evidence` object
(e.g. an OR15 artifact belonging to a different instrument) can never
raise a `ValueError` for a `NOT_ACTIONABLE` result; it can only ever
raise once that evidence is actually relevant to a TRADE+QUALIFIED
candidate.

Mandatory V0 layer-3 evidence is deliberately minimal (ID-7B2.1 §14): a
completed M5 checkpoint candle and the session VWAP price. No D1 ATR, no
RS/RVOL/Gap gate, no extension cutoff, no generic support/resistance, no
DarvaX. `IntradaySignalSet.vwap` (`VwapEvidence`, ID-2) deliberately
carries only the categorical relation + `deviation_pct` it was formalized
for — not the raw VWAP price V0's `EntryLocationContext`/
`OperativeInvalidation` value objects need — so this module defines its
own narrow `EntryActionabilityMarketEvidence` input context carrying the
raw price directly (`indicators.calculations.vwap`'s own first return
value) rather than re-deriving it from a wider indicator object, per the
ID-7C authorization's "smallest representation after source audit" and
"no parallel market-data domain" instructions.

Option 1 (canonical-cycle synchronous, ADR-015): V0 sets
`entry_actionability_as_of = entry_qualification.as_of` unconditionally —
the same checkpoint the bound EQ was itself evaluated at. This does NOT
exercise ADR-015's future same-EQ re-evaluation capability (a strictly
later `entry_actionability_as_of` remains structurally valid in the
domain model, ID-7A.1) — V0's methodology has no use for it yet; a later
milestone may introduce a genuine re-evaluation caller without any domain
or engine change required to support it.

Contract-error vs. methodology-UNKNOWN boundary (ID-7C authorization item
37, finalized by ID-7C.1): a Decision/EQ identity mismatch, a malformed
input object, a naive mandatory timestamp, or evidence timestamped after
the checkpoint is a programmer/caller contract violation — this engine
raises `ValueError` deterministically, exactly like
`EntryQualificationEngine`'s own `_validate_input_coherence`. Genuinely
missing or geometrically invalid market evidence is a real methodology
outcome (`UNKNOWN`), never converted into a raised exception.

ID-7C.1 (owner source-review correction) closed three narrow gaps the
core evaluator's own frozen V0 behavior did not need reopened: (1) the
raw VWAP price had no market-time provenance, so nothing proved it was
computed from the same evidence checkpoint as the M5 entry reference —
`EntryActionabilityMarketEvidence` gained `session_vwap_as_of`, frozen
pairing with `session_vwap`, and an exact-equality check against the
candle's own completion instant whenever both are supplied; (2) a
supplied `opening_range_15` was checked only for OR15-window identity,
never for actually describing the same instrument/session/checkpoint —
`_validate_or15_coherence` now proves that before the engine ever
consumes or attaches it; (3) `EntryActionabilityPolicy` used to accept
an arbitrary caller-supplied `methodology_version`, letting identical V0
behavior claim a different, uncalibrated methodology identity — the
field was removed entirely; this engine's emitted methodology version is
now always the frozen `DEFAULT_METHODOLOGY_VERSION`, unconditionally.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from athena.domain.decision import Decision
from athena.domain.enums import DecisionType, Direction, Timeframe
from athena.domain.market import Candle
from athena.intraday.entry_actionability_models import (
    DEFAULT_METHODOLOGY_VERSION,
    T1_GOAL_BAND_PCT,
    T2_GOAL_BAND_PCT,
    EntryActionability,
    EntryActionabilityReasonCode,
    EntryActionabilityState,
    EntryLocationContext,
    EntryReference,
    EntryReferenceBasis,
    InvalidationBasis,
    OpeningRangeContextBasis,
    OpeningRangeContextReference,
    OperativeInvalidation,
    RewardBasis,
    RewardReference,
)
from athena.intraday.entry_qualification_models import EntryQualification, EntryQualificationState
from athena.intraday.opening_range_models import (
    OpeningRangeEvidence,
    OpeningRangeFormationStatus,
    OpeningRangeWindow,
)
from athena.session.engine import is_candle_completed

#: M5 bar duration. A small, local constant rather than importing
#: `session.engine`'s module-private `_TIMEFRAME_MINUTES` — mirrors that
#: module's own stated rationale (duplicating a 1-entry unit fact is
#: preferable to reaching into another module's private state).
_M5_BAR_DURATION = timedelta(minutes=5)


@dataclass(frozen=True, slots=True)
class EntryActionabilityMarketEvidence:
    """Narrow ID-7C evaluation-input context — exactly the layer-3 market
    evidence the frozen V0 methodology consumes, nothing more (ID-7C
    authorization items 35/36: no parallel market-data domain, no
    over-denormalization). Reuses canonical `Candle`/`OpeningRangeEvidence`
    directly rather than re-modeling them; RS/RVOL/Gap/M15-trend/D1-ATR/
    generic-S-R/other-OR-lifecycle-events are deliberately absent — none
    of them are part of the frozen V0 contract.

    ``completed_m5_close`` must be the exact, already-selected completed
    M5 checkpoint candle — never a forming bar, never a different
    timeframe, never resolved by this engine from a wider series (no
    repository/provider access exists here; the caller is responsible for
    candle selection, e.g. via `athena.session.engine.latest_completed_candle`).
    ``None`` means "no completed M5 checkpoint candle was supplied" — a
    legitimate real-world case (`INSUFFICIENT_EVIDENCE`), not a contract
    error.

    ``session_vwap`` is the raw session VWAP price
    (`indicators.calculations.vwap`'s own first return value). ``None``
    means "VWAP could not be computed this cycle" — legitimate missing
    market evidence (`INSUFFICIENT_EVIDENCE`), never a contract error. A
    non-``None`` value must be strictly positive — a non-positive VWAP is
    a malformed, impossible market-evidence value (`ValueError`), never
    methodology `UNKNOWN` (ID-7C.1 authorization item 9's own explicit
    distinction: ``None`` = legitimate absence -> `UNKNOWN`; non-positive
    = impossible value -> contract error).

    ``session_vwap_as_of`` (ID-7C.1) is ``session_vwap``'s own market-time
    provenance — the checkpoint the VWAP price was actually computed
    through. Frozen pairing: present iff ``session_vwap`` is present (a
    price with no provenance, or provenance with no price, is malformed
    input). When ``completed_m5_close`` is also supplied, V0's own frozen
    PIT semantics (ID-7B.2.1 §14: "the last completed M5 bar used for the
    checkpoint's VWAP / entry evidence") require it to equal that candle's
    own completion instant exactly — proving the M5 entry reference and
    the VWAP invalidation/location evidence share ONE coherent evidence
    checkpoint, not two independently-stale-or-future readings.

    ``opening_range_15`` is the full canonical `OpeningRangeEvidence`
    (OR15 window only) — always-optional, purely contextual (ID-7B.2.1
    §14): its absence, or a non-`COMPLETE` formation, never forces
    `UNKNOWN` and is never substituted for the operative VWAP-loss
    invalidation. Its own instrument/session/point-in-time coherence
    against the candidate being evaluated is validated at `evaluate()`
    time (ID-7C.1), not here, since that requires the resolved Decision/
    EQ identity and checkpoint this narrow context does not itself carry.
    """

    completed_m5_close: Candle | None
    session_vwap: Decimal | None
    session_vwap_as_of: datetime | None
    opening_range_15: OpeningRangeEvidence | None

    def __post_init__(self) -> None:
        if (
            self.completed_m5_close is not None
            and self.completed_m5_close.timeframe is not Timeframe.M5
        ):
            raise ValueError(
                "EntryActionabilityMarketEvidence.completed_m5_close must be an M5 "
                f"candle, got {self.completed_m5_close.timeframe.value}"
            )
        if self.session_vwap is not None and self.session_vwap <= 0:
            raise ValueError("EntryActionabilityMarketEvidence.session_vwap must be positive")
        if (self.session_vwap is None) != (self.session_vwap_as_of is None):
            raise ValueError(
                "EntryActionabilityMarketEvidence.session_vwap and session_vwap_as_of "
                "must both be present or both be None — a price with no provenance, or "
                "provenance with no price, is malformed input"
            )
        if self.session_vwap_as_of is not None and self.session_vwap_as_of.tzinfo is None:
            raise ValueError(
                "EntryActionabilityMarketEvidence.session_vwap_as_of must be timezone-aware"
            )
        if self.completed_m5_close is not None and self.session_vwap_as_of is not None:
            m5_completion = self.completed_m5_close.ts_open + _M5_BAR_DURATION
            if self.session_vwap_as_of != m5_completion:
                raise ValueError(
                    "EntryActionabilityMarketEvidence.session_vwap_as_of "
                    f"({self.session_vwap_as_of.isoformat()}) must equal completed_m5_close's "
                    f"own completion instant ({m5_completion.isoformat()}) — V0 requires the M5 "
                    "entry reference and VWAP evidence to share one coherent evidence checkpoint"
                )
        if (
            self.opening_range_15 is not None
            and self.opening_range_15.formation.window is not OpeningRangeWindow.OR15
        ):
            raise ValueError(
                "EntryActionabilityMarketEvidence.opening_range_15 must be an OR15 "
                f"window, got {self.opening_range_15.formation.window.value}"
            )


@dataclass(frozen=True, slots=True)
class EntryActionabilityPolicy:
    """Audit-metadata-only companion to `evaluate()` (ID-7C.1).

    Deliberately carries NO methodology-version field. This class is
    specifically the V0 deterministic evaluator — its methodology
    identity is `DEFAULT_METHODOLOGY_VERSION`
    (`"entry-actionability-v0"`), always, unconditionally; earlier code
    let a caller supply an arbitrary `methodology_version` string while
    the engine ran the identical frozen V0 algorithm underneath, which
    would have let an artifact claim a methodology lineage it did not
    actually execute (a methodology identity must identify methodology
    *behavior*, not caller labeling). A genuine future methodology
    version requires a new evaluator implementation or explicit
    version-aware dispatch — never merely a different identity string
    over this same V0 code (ID-7C.1 authorization item 20; no
    methodology registry is introduced here).

    `config_snapshot_id` is retained as optional audit metadata only,
    mirroring `EntryQualificationPolicy`'s own field for symmetry — but
    unlike EQ's `EntryQualification.config_snapshot_id`, `EntryActionability`
    has no corresponding field at all, so this value is NOT propagated
    into the emitted artifact and cannot change V0 behavior in any way.
    """

    config_snapshot_id: str | None = None

    def __post_init__(self) -> None:
        if self.config_snapshot_id is not None and not self.config_snapshot_id:
            raise ValueError("EntryActionabilityPolicy.config_snapshot_id cannot be empty")


class EntryActionabilityEngine:
    """Deterministic, side-effect-free V0 methodology evaluator.

    O(1) per candidate: no candle-series iteration, no repository access,
    no provider/network call, no history scan, no lookup of any prior
    `EntryActionability`. `evaluate()` is the only public method.
    """

    def evaluate(
        self,
        *,
        decision: Decision,
        entry_qualification: EntryQualification,
        market_evidence: EntryActionabilityMarketEvidence,
        evaluated_at: datetime,
        policy: EntryActionabilityPolicy | None = None,
    ) -> EntryActionability:
        """``policy`` accepts only inert audit metadata
        (`EntryActionabilityPolicy.config_snapshot_id`) — see that class's
        own docstring (ID-7C.1). It is never read here: the emitted
        artifact's methodology version is always the frozen
        `DEFAULT_METHODOLOGY_VERSION`, never a caller-relabeled string."""
        if evaluated_at.tzinfo is None:
            raise ValueError("EntryActionabilityEngine.evaluate evaluated_at must be timezone-aware")

        instrument_id = _validate_binding(decision, entry_qualification)
        entry_actionability_as_of = entry_qualification.as_of  # Option 1: same checkpoint as EQ.

        # ID-7C.2: upstream methodology gates are computed and short-circuit
        # IMMEDIATELY after exact Decision/EQ binding validation — before
        # any candidate/checkpoint-relative layer-3 evidence check
        # (candle coherence, VWAP-provenance-vs-checkpoint, OR15
        # coherence). Layer-3 evidence is irrelevant to an upstream-
        # ineligible candidate's historical methodology verdict, so it
        # must never be inspected for one — an OR15 artifact belonging to
        # another instrument, or a candle that has not yet completed, must
        # not raise a ValueError for a WATCH Decision or a non-QUALIFIED
        # EQ; the correct result is simply NOT_ACTIONABLE. Only exact
        # Decision/EQ identity mismatches remain unconditional contract
        # errors (checked above, by `_validate_binding`), since a
        # mismatched binding can never be trusted to produce ANY verdict,
        # eligible or not.
        reasons: list[EntryActionabilityReasonCode] = []
        if decision.decision_type is not DecisionType.TRADE:
            reasons.append(EntryActionabilityReasonCode.UPSTREAM_DECISION_NOT_TRADE)
        if entry_qualification.state is not EntryQualificationState.QUALIFIED:
            reasons.append(EntryActionabilityReasonCode.UPSTREAM_EQ_NOT_QUALIFIED)

        if reasons:
            return self._emit(
                decision, entry_qualification, instrument_id, entry_actionability_as_of,
                evaluated_at,
                state=EntryActionabilityState.NOT_ACTIONABLE,
                reason_codes=tuple(reasons),
                evidence_as_of=None,
                entry_reference=None, entry_location_context=None,
                operative_invalidation=None, reward=None, opening_range_context=None,
                explanation=_upstream_gate_explanation(decision, entry_qualification, reasons),
            )

        # Upstream eligibility satisfied: Decision == TRADE, exact EQ ==
        # QUALIFIED. Candidate/checkpoint-relative layer-3 evidence
        # validation — and layer-3 evidence sufficiency itself — may now
        # run, never before this point (ID-7A.2's own frozen invariant,
        # sharpened by ID-7C.2 to also cover evidence *validation*, not
        # just evidence *consumption*).
        if market_evidence.completed_m5_close is not None:
            _validate_candle_coherence(
                market_evidence.completed_m5_close, instrument_id, entry_actionability_as_of
            )
        if (
            market_evidence.session_vwap_as_of is not None
            and market_evidence.session_vwap_as_of > entry_actionability_as_of
        ):
            raise ValueError(
                "EntryActionabilityEngine received session_vwap_as_of "
                f"({market_evidence.session_vwap_as_of.isoformat()}) later than the "
                f"checkpoint ({entry_actionability_as_of.isoformat()}) — future VWAP "
                "evidence relative to the checkpoint is a contract error, not a "
                "methodology outcome"
            )
        if market_evidence.opening_range_15 is not None:
            _validate_or15_coherence(
                market_evidence.opening_range_15, instrument_id,
                entry_qualification.session_date, entry_actionability_as_of,
            )

        candle = market_evidence.completed_m5_close
        vwap = market_evidence.session_vwap
        if candle is None or vwap is None:
            missing = _describe_missing_evidence(candle, vwap)
            return self._emit(
                decision, entry_qualification, instrument_id, entry_actionability_as_of,
                evaluated_at,
                state=EntryActionabilityState.UNKNOWN,
                reason_codes=(EntryActionabilityReasonCode.INSUFFICIENT_EVIDENCE,),
                evidence_as_of=None,
                entry_reference=None, entry_location_context=None,
                operative_invalidation=None, reward=None, opening_range_context=None,
                explanation=(
                    "UNKNOWN: upstream eligible (TRADE + QUALIFIED) but required V0 "
                    f"checkpoint evidence is unavailable — {missing}."
                ),
            )

        entry_price = candle.close
        # ID-7C.1: EntryActionabilityMarketEvidence.__post_init__ already
        # proved session_vwap_as_of == candle.ts_open + _M5_BAR_DURATION
        # whenever both are supplied (which they are, past this point) —
        # this is the single proven common evidence boundary for both the
        # M5 entry reference and the VWAP location/invalidation evidence.
        evidence_as_of = candle.ts_open + _M5_BAR_DURATION
        entry_reference = EntryReference(
            price=entry_price, basis=EntryReferenceBasis.QUALIFYING_M5_CLOSE
        )
        deviation_pct = (entry_price - vwap) / vwap * Decimal(100)
        entry_location_context = EntryLocationContext(
            vwap=vwap, vwap_deviation_pct=deviation_pct
        )

        if not _geometry_valid(decision.direction, entry_price, vwap):
            return self._emit(
                decision, entry_qualification, instrument_id, entry_actionability_as_of,
                evaluated_at,
                state=EntryActionabilityState.UNKNOWN,
                reason_codes=(EntryActionabilityReasonCode.INVALIDATION_UNAVAILABLE,),
                evidence_as_of=evidence_as_of,
                entry_reference=None, entry_location_context=None,
                operative_invalidation=None, reward=None, opening_range_context=None,
                explanation=(
                    "UNKNOWN: upstream eligible and checkpoint evidence available, but the "
                    f"VWAP-loss operative invalidation is not valid for direction "
                    f"{decision.direction.value} (VWAP={vwap}, entry={entry_price})."
                ),
            )

        operative_invalidation = OperativeInvalidation(level=vwap, basis=InvalidationBasis.VWAP_LOSS)
        reward = _reward_reference(decision.direction, entry_price, vwap)
        opening_range_context = _opening_range_context(
            decision.direction, market_evidence.opening_range_15
        )

        return self._emit(
            decision, entry_qualification, instrument_id, entry_actionability_as_of,
            evaluated_at,
            state=EntryActionabilityState.ACTIONABLE,
            reason_codes=(),
            evidence_as_of=evidence_as_of,
            entry_reference=entry_reference,
            entry_location_context=entry_location_context,
            operative_invalidation=operative_invalidation,
            reward=reward,
            opening_range_context=opening_range_context,
            explanation=(
                f"ACTIONABLE: TRADE + QUALIFIED; entry={entry_price} (completed M5 close); "
                f"VWAP-loss invalidation={vwap}; T1={reward.t1_price}, T2={reward.t2_price} "
                "goal bands (informational RR)."
            ),
        )

    @staticmethod
    def _emit(
        decision: Decision,
        entry_qualification: EntryQualification,
        instrument_id: str,
        entry_actionability_as_of: datetime,
        evaluated_at: datetime,
        *,
        state: EntryActionabilityState,
        reason_codes: tuple[EntryActionabilityReasonCode, ...],
        evidence_as_of: datetime | None,
        entry_reference: EntryReference | None,
        entry_location_context: EntryLocationContext | None,
        operative_invalidation: OperativeInvalidation | None,
        reward: RewardReference | None,
        opening_range_context: OpeningRangeContextReference | None,
        explanation: str,
    ) -> EntryActionability:
        return EntryActionability(
            instrument_id=instrument_id,
            session_date=entry_qualification.session_date,
            entry_qualification_as_of=entry_qualification.as_of,
            decision_id=entry_qualification.decision_id,
            entry_qualification_methodology_version=entry_qualification.methodology_version,
            entry_actionability_as_of=entry_actionability_as_of,
            entry_actionability_methodology_version=DEFAULT_METHODOLOGY_VERSION,
            decision_type=decision.decision_type,
            direction=decision.direction,
            entry_qualification_state=entry_qualification.state,
            run_id=decision.run_id,
            cycle_id=decision.cycle_id,
            state=state,
            reason_codes=reason_codes,
            evidence_finality=entry_qualification.evidence_finality,
            evidence_as_of=evidence_as_of,
            entry_reference=entry_reference,
            entry_location_context=entry_location_context,
            operative_invalidation=operative_invalidation,
            reward=reward,
            opening_range_context=opening_range_context,
            evaluated_at=evaluated_at,
            explanation=explanation,
        )


def _validate_binding(decision: Decision, eq: EntryQualification) -> str:
    """Prove ``decision``/``eq`` describe ONE exact, coherent candidate
    before any methodology evaluation — mirrors
    `EntryQualificationEngine`'s own `_validate_input_coherence` and the
    repository's own `_validate_entry_actionability_decision_binding`/
    `_validate_entry_actionability_eq_binding` (ID-7A), applied here at
    evaluation time instead of persistence time. A mismatch is a
    programmer/input-contract error — never a methodology UNKNOWN — and
    is never silently repaired. Returns the resolved instrument_id
    (mirrors `EntryQualificationEngine`'s own `_resolve_instrument_id`
    fallback when `Decision.instrument_id` is `None`)."""
    if eq.decision_id != decision.decision_id:
        raise ValueError(
            "EntryActionabilityEngine received an EntryQualification bound to "
            f"decision_id={eq.decision_id!r} but a Decision with "
            f"decision_id={decision.decision_id!r} — not an exact bound pair"
        )
    if eq.decision_type != decision.decision_type:
        raise ValueError(
            "EntryActionabilityEngine received a Decision/EntryQualification pair "
            f"with disagreeing decision_type (Decision={decision.decision_type.value!r}, "
            f"EntryQualification={eq.decision_type.value!r})"
        )
    if eq.run_id != decision.run_id:
        raise ValueError(
            "EntryActionabilityEngine received a Decision/EntryQualification pair "
            f"with disagreeing run_id (Decision={decision.run_id!r}, "
            f"EntryQualification={eq.run_id!r})"
        )
    if eq.cycle_id != decision.cycle_id:
        raise ValueError(
            "EntryActionabilityEngine received a Decision/EntryQualification pair "
            f"with disagreeing cycle_id (Decision={decision.cycle_id!r}, "
            f"EntryQualification={eq.cycle_id!r})"
        )
    if decision.instrument_id is None:
        return eq.instrument_id
    if decision.instrument_id != eq.instrument_id:
        raise ValueError(
            "EntryActionabilityEngine received a Decision "
            f"({decision.instrument_id!r}) and EntryQualification "
            f"({eq.instrument_id!r}) for two different instruments"
        )
    return decision.instrument_id


def _validate_candle_coherence(candle: Candle, instrument_id: str, checkpoint: datetime) -> None:
    if candle.instrument_id != instrument_id:
        raise ValueError(
            "EntryActionabilityEngine received a completed_m5_close candle for "
            f"{candle.instrument_id!r}, but the resolved candidate instrument is "
            f"{instrument_id!r}"
        )
    if not is_candle_completed(candle, as_of=checkpoint):
        raise ValueError(
            "EntryActionabilityEngine received a completed_m5_close candle "
            f"(ts_open={candle.ts_open.isoformat()}) that has not actually completed as of "
            f"the checkpoint ({checkpoint.isoformat()}) — future evidence relative to the "
            "checkpoint is a contract error, not a methodology outcome"
        )


def _validate_or15_coherence(
    or15: OpeningRangeEvidence, instrument_id: str, session_date: date, checkpoint: datetime
) -> None:
    """OR15 is non-gating, but a supplied artifact must still be truthful
    about which candidate/checkpoint it describes before this engine
    consumes (or attaches) it (ID-7C.1 gap 2). A cross-instrument,
    cross-session, or future OR15 artifact is a contract error, never
    silently ignored merely because OR15 itself is optional — "optional"
    means absence/non-`COMPLETE` is allowed, not that incoherent supplied
    evidence is.

    `formation.range_end > checkpoint` is deliberately NOT re-checked
    here: `OpeningRangeEngine` itself only ever sets
    `status = COMPLETE` when its own `as_of >= range_end`
    (audited at source — `opening_range_engine.py`'s own status-assignment
    branch), so `status == COMPLETE` already guarantees `range_end <=
    or15.as_of`; combined with the `or15.as_of <= checkpoint` check below,
    `range_end <= checkpoint` follows transitively without a duplicate
    check.
    """
    if or15.instrument_id != instrument_id:
        raise ValueError(
            "EntryActionabilityEngine received an opening_range_15 for "
            f"{or15.instrument_id!r}, but the resolved candidate instrument is "
            f"{instrument_id!r}"
        )
    if or15.session_date != session_date:
        raise ValueError(
            "EntryActionabilityEngine received an opening_range_15 for session "
            f"{or15.session_date!r}, but the bound EntryQualification's session is "
            f"{session_date!r}"
        )
    if or15.as_of > checkpoint:
        raise ValueError(
            f"EntryActionabilityEngine received an opening_range_15 as_of "
            f"({or15.as_of.isoformat()}) later than the checkpoint "
            f"({checkpoint.isoformat()}) — future OR15 evidence relative to the "
            "checkpoint is a contract error, not a methodology outcome"
        )


def _describe_missing_evidence(candle: Candle | None, vwap: Decimal | None) -> str:
    missing = []
    if candle is None:
        missing.append("no completed M5 checkpoint candle")
    if vwap is None:
        missing.append("no session VWAP")
    return ", ".join(missing)


def _upstream_gate_explanation(
    decision: Decision, eq: EntryQualification, reasons: list[EntryActionabilityReasonCode]
) -> str:
    parts = []
    if EntryActionabilityReasonCode.UPSTREAM_DECISION_NOT_TRADE in reasons:
        parts.append(f"Decision is {decision.decision_type.value}, not TRADE")
    if EntryActionabilityReasonCode.UPSTREAM_EQ_NOT_QUALIFIED in reasons:
        parts.append(f"bound EntryQualification is {eq.state.value}, not QUALIFIED")
    return "NOT_ACTIONABLE: " + "; ".join(parts) + "."


def _geometry_valid(direction: Direction, entry_price: Decimal, invalidation_level: Decimal) -> bool:
    """Mirrors `EntryActionability._validate_risk_geometry`'s exact
    structural rule — checked here BEFORE domain construction so a
    geometrically invalid checkpoint maps deterministically to
    `UNKNOWN`/`INVALIDATION_UNAVAILABLE` (ID-7C authorization item 19),
    never a raised domain `ValueError` escaping as an unexpected
    programming error. `Decision.__post_init__` already guarantees
    `direction` is `LONG` or `SHORT` whenever `decision_type == TRADE`
    (the only branch that reaches this function), so `Direction.NONE`
    is structurally unreachable here."""
    if direction is Direction.LONG:
        return invalidation_level < entry_price
    if direction is Direction.SHORT:
        return invalidation_level > entry_price
    raise ValueError(
        f"EntryActionabilityEngine cannot evaluate risk geometry for direction {direction.value} "
        "— a TRADE Decision must be LONG or SHORT (Decision.__post_init__ already guarantees this)"
    )


def _reward_reference(direction: Direction, entry_price: Decimal, invalidation_level: Decimal) -> RewardReference:
    """T1/T2 goal bands (ID-7B.2's frozen `T1_GOAL_BAND_PCT`/
    `T2_GOAL_BAND_PCT`) plus informational-only RR — exact Decimal
    arithmetic throughout, no rounding/tick-size policy (none was
    frozen)."""
    if direction is Direction.LONG:
        t1_price = entry_price * (Decimal(1) + T1_GOAL_BAND_PCT)
        t2_price = entry_price * (Decimal(1) + T2_GOAL_BAND_PCT)
    else:
        assert direction is Direction.SHORT  # guaranteed reachable-only value; see _geometry_valid
        t1_price = entry_price * (Decimal(1) - T1_GOAL_BAND_PCT)
        t2_price = entry_price * (Decimal(1) - T2_GOAL_BAND_PCT)

    risk_distance = abs(entry_price - invalidation_level)
    reward_distance_t1 = abs(t1_price - entry_price)
    reward_distance_t2 = abs(t2_price - entry_price)
    return RewardReference(
        t1_price=t1_price,
        t2_price=t2_price,
        basis=RewardBasis.GOAL_BANDS_ONLY,
        reward_risk_to_t1=reward_distance_t1 / risk_distance,
        reward_risk_to_t2=reward_distance_t2 / risk_distance,
    )


def _opening_range_context(
    direction: Direction, or15: OpeningRangeEvidence | None
) -> OpeningRangeContextReference | None:
    """Always-optional, purely contextual — absence (FORMING/INCOMPLETE_DATA/
    NOT_AVAILABLE/NOT_APPLICABLE/missing) never changes the ACTIONABLE
    verdict, never substitutes for the operative VWAP-loss invalidation,
    and never feeds RR (ID-7B.2.1 §14). The directionally coherent
    structural boundary is the range low for LONG (the level below which
    the setup's own opening structure was already violated) and the range
    high for SHORT — a price level only, never a breakout-event or
    DarvaX-style label."""
    if or15 is None or or15.formation.status is not OpeningRangeFormationStatus.COMPLETE:
        return None
    level = or15.formation.low if direction is Direction.LONG else or15.formation.high
    if level is None or level <= 0:
        return None
    return OpeningRangeContextReference(level=level, basis=OpeningRangeContextBasis.OR15_BOUNDARY)
