"""Entry Qualification domain contracts (ID-6A).

Advisory-only contracts for the future ID-6B engine. These types answer
"is this already-produced canonical Decision actionable now?" without
deciding that answer here. No thresholds, no workflow wiring, no
persistence, no Entry/TradePlan, no order behavior.

ADR-013 freezes three independent dimensions: qualification state,
evidence finality/provenance, and qualification confirmation. They remain
orthogonal here by construction.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum, unique

from athena.domain.enums import DecisionType


@unique
class EntryQualificationState(str, Enum):
    """What ATHENA currently concludes about intraday actionability.

    State never encodes evidence finality or methodology confirmation.
    ``UNKNOWN`` means ATHENA cannot honestly determine actionability;
    ``NOT_YET`` means the candidate is structurally eligible but not
    actionable now and may still become actionable later this session.
    """

    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    UNKNOWN = "UNKNOWN"
    NOT_YET = "NOT_YET"
    QUALIFIED = "QUALIFIED"
    DISQUALIFIED_FOR_SESSION = "DISQUALIFIED_FOR_SESSION"
    EXPIRED = "EXPIRED"


@unique
class EntryEvidenceFinality(str, Enum):
    """Finality/provenance of the decisive evidence behind the conclusion.

    ``NO_DECISIVE_PROVISIONAL_M5_DEPENDENCY`` does not claim provider
    settlement, historical immutability, or bitemporal reconstruction. It
    means only that the decisive evidence is not known to depend on
    provider-provisional live M5.
    """

    UNKNOWN_PROVENANCE = "UNKNOWN_PROVENANCE"
    LIVE_M5_PROVISIONAL = "LIVE_M5_PROVISIONAL"
    NO_DECISIVE_PROVISIONAL_M5_DEPENDENCY = "NO_DECISIVE_PROVISIONAL_M5_DEPENDENCY"


@unique
class EntryQualificationConfirmation(str, Enum):
    """Methodology confirmation status, separate from evidence finality."""

    UNKNOWN = "UNKNOWN"
    NOT_EVALUATED = "NOT_EVALUATED"
    NOT_CONFIRMED = "NOT_CONFIRMED"
    CONFIRMED_BY_POLICY = "CONFIRMED_BY_POLICY"


@unique
class EntryQualificationReasonCode(str, Enum):
    """Structural/lifecycle/data-quality reason vocabulary for ID-6A.

    Methodology-specific reasons such as RVOL/ORB/RS/VWAP failures are
    deliberately absent; ID-6B+ owns any future methodology rule vocabulary.
    """

    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    STALE_EVIDENCE = "STALE_EVIDENCE"
    PROVENANCE_UNKNOWN = "PROVENANCE_UNKNOWN"
    DECISION_SUPERSEDED = "DECISION_SUPERSEDED"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    STRUCTURALLY_OUT_OF_SCOPE = "STRUCTURALLY_OUT_OF_SCOPE"


@unique
class EntryQualificationEvidenceKind(str, Enum):
    """Upstream artifact families an EntryQualification may reference."""

    DECISION = "DECISION"
    SESSION_CONTEXT = "SESSION_CONTEXT"
    INTRADAY_SIGNAL_SET = "INTRADAY_SIGNAL_SET"
    OTHER = "OTHER"


@dataclass(frozen=True, slots=True)
class EntryQualificationEvidenceRef:
    """Minimal explainability/audit reference to an upstream artifact.

    ``ref_id`` is optional because several current ID artifacts are live
    value objects without canonical persisted identities. This reference
    names what was used without pretending to provide bitemporal replay.
    """

    kind: EntryQualificationEvidenceKind
    ref_id: str | None
    as_of: datetime | None
    explanation: str

    def __post_init__(self) -> None:
        if self.ref_id is not None and not self.ref_id:
            raise ValueError("EntryQualificationEvidenceRef.ref_id cannot be empty")
        if self.as_of is not None and self.as_of.tzinfo is None:
            raise ValueError("EntryQualificationEvidenceRef.as_of must be timezone-aware")
        if not self.explanation:
            raise ValueError("EntryQualificationEvidenceRef.explanation is mandatory (ADR-005)")


@dataclass(frozen=True, slots=True)
class EntryQualification:
    """Immutable ID-6A contract for one Decision's intraday actionability.

    This object is a future engine output, not an engine. It binds to the
    canonical Decision it evaluates, preserves run/cycle provenance for the
    qualification observation, and carries its explanation at creation time
    per ADR-005.
    """

    instrument_id: str
    session_date: date
    as_of: datetime
    run_id: str
    cycle_id: str
    decision_id: str
    decision_type: DecisionType
    state: EntryQualificationState
    evidence_finality: EntryEvidenceFinality
    confirmation: EntryQualificationConfirmation
    reason_codes: tuple[EntryQualificationReasonCode, ...]
    evidence_refs: tuple[EntryQualificationEvidenceRef, ...]
    methodology_version: str | None
    config_snapshot_id: str | None
    explanation: str

    def __post_init__(self) -> None:
        for name in ("instrument_id", "run_id", "cycle_id", "decision_id"):
            if not getattr(self, name):
                raise ValueError(f"EntryQualification.{name} is mandatory")
        if self.as_of.tzinfo is None:
            raise ValueError("EntryQualification.as_of must be timezone-aware")
        if self.methodology_version is not None and not self.methodology_version:
            raise ValueError("EntryQualification.methodology_version cannot be empty")
        if self.config_snapshot_id is not None and not self.config_snapshot_id:
            raise ValueError("EntryQualification.config_snapshot_id cannot be empty")
        if len(set(self.reason_codes)) != len(self.reason_codes):
            raise ValueError("EntryQualification.reason_codes must not contain duplicates")
        if not self.explanation:
            raise ValueError("EntryQualification.explanation is mandatory (ADR-005)")
