"""Evidence-finality resolution for Entry Qualification (ID-6D).

`EntryQualificationEngine.evaluate()` requires `EntryEvidenceFinality` as an
explicit caller input (ID-6B.2) and only ever echoes it through unchanged
(ID-6B.2A/ID-6C never infer or rewrite it). This module supplies that input
honestly, for the first time, without inventing a second methodology engine
and without reading a wall clock.

Two provenance dimensions matter (ADR-013):

1. Direct dependence — do the readiness inputs the engine actually reads
   (VWAP, aggregate trend, Relative Strength, Relative Volume) come from
   current-session, possibly-still-provisional M5 candles?
2. Indirect dependence — does the bound canonical Decision's own decisive
   evidence (via ScoringEngine/ConfidenceEngine, upstream of Entry
   Qualification) depend on the same provisional M5 evidence?

Source-verified direct provenance (`src/athena/ops/owner_validation.py`):
VWAP reads `Timeframe.M5` candles; the trend context's 5m leg reads
`Timeframe.M5`, its 15m leg `Timeframe.M15`; RelativeStrengthContext reads
`Timeframe.M5` for stock/market/sector; RelativeVolumeContext reads
`Timeframe.M5` history. All four families the frozen v0 expression consumes
are M5-derived (trend jointly with M15). `live_m5_settlement_repair.py`'s
own docstring confirms "today's still-open/most-recent session is never in
scope for this backfill" — i.e. a currently-active session's M5 has not yet
been through settlement repair.

`EntryQualificationEngine`'s own state precedence (unchanged, not
duplicated here) means the pure engine reads `IntradaySignalSet` at all
*only* when `decision.decision_type in (WATCH, TRADE)` AND
`session_context.phase is SessionPhase.REGULAR` — every other combination
(`OUT_OF_SCOPE`, `EXPIRED`, or `NOT_YET` from `PRE_OPEN`) is a structural/
lifecycle short-circuit that never touches direct evidence at all. This
resolver reuses exactly that same two-condition eligibility gate — the
engine's own publicly documented structural/lifecycle precondition, not its
inner VWAP/trend/RS-or-RVOL tri-state formula — to decide whether direct
evidence was consulted, so it never re-implements the readiness methodology
itself (owner instruction: "must not become a second Entry Qualification
engine"). Because this gate is checked *before* the engine is called
(finality is a required *input* to `evaluate()`, so it cannot be derived
from the engine's own output without a wasteful/awkward second invocation),
no reason-code introspection is needed either.

Indirect (Decision) provenance cannot currently be positively established:
ADR-013 and ID-6B.0 already recorded that canonical Decision provenance is
insufficient to prove whether a Decision was materially influenced by
provisional live M5 evidence, and this module does not retrofit
`DecisionEngine`/`DecisionTrace` to change that. Consequently
`NO_DECISIVE_PROVISIONAL_M5_DEPENDENCY` — which requires positive proof
that *neither* direct nor indirect evidence depends on provisional M5 — is
structurally unreachable under the current runtime. See
`docs/design/ID-6D-ENTRY-QUALIFICATION-WORKFLOW-INTEGRATION.md` §"Provenance
limitation report" for the full accounting.
"""

from __future__ import annotations

from athena.domain.decision import Decision
from athena.domain.enums import DecisionType
from athena.intraday.entry_qualification_models import EntryEvidenceFinality
from athena.session.models import SessionContext, SessionPhase

_ELIGIBLE_DECISION_TYPES = (DecisionType.WATCH, DecisionType.TRADE)


def resolve_evidence_finality(
    decision: Decision, session_context: SessionContext
) -> EntryEvidenceFinality:
    """Resolve the `EntryEvidenceFinality` to supply to
    `EntryQualificationEngine.evaluate()` for one candidate.

    Returns `LIVE_M5_PROVISIONAL` whenever the pure engine will actually
    reach its REGULAR-phase readiness evaluation for this candidate (the
    same two-condition precondition the engine itself checks:
    `decision.decision_type` eligible AND `session_context.phase is
    SessionPhase.REGULAR`) — every direct evidence family the frozen v0
    expression consumes in that case is source-verified M5-derived, and
    `SessionPhase.REGULAR` means the session is currently active relative
    to `session_context.as_of`, the same window
    `live_m5_settlement_repair.py` itself excludes from settlement repair.

    Returns `UNKNOWN_PROVENANCE` otherwise (`OUT_OF_SCOPE`, `EXPIRED`, or
    `NOT_YET` from `PRE_OPEN` — no direct evidence is consulted at all) —
    deferring to indirect Decision provenance, which the current runtime
    cannot positively establish (ADR-013).

    Never returns `NO_DECISIVE_PROVISIONAL_M5_DEPENDENCY`: that requires
    positive proof neither dimension depends on provisional M5, and no
    current contract can establish the Decision side of that proof.

    Pure and deterministic: no clock read, no repository access, no
    provider call — `decision`/`session_context` are the only inputs, both
    already available to the caller.
    """
    if (
        decision.decision_type in _ELIGIBLE_DECISION_TYPES
        and session_context.phase is SessionPhase.REGULAR
    ):
        return EntryEvidenceFinality.LIVE_M5_PROVISIONAL
    return EntryEvidenceFinality.UNKNOWN_PROVENANCE
