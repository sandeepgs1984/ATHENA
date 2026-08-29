"""Relative Volume Context (ID-5D).

Answers: "is this stock trading more or less volume today, through this
exact point in the session, than it typically does through the same
point in the session?" — descriptive only, never "should I enter." Uses
CUMULATIVE SAME-TIME-OF-DAY relative volume: today's cumulative canonical
completed M5 volume from session open through an explicit cutoff, divided
by the arithmetic mean of the SAME cumulative-through-the-same-cutoff
figure across every historical settled session for which that comparison
is genuinely possible (audited and chosen over single-bar or full-day
comparison — see the ID-5D Milestone Review Summary's audit section; a
single-bar comparison is too noisy, and comparing a partial session
against historical FULL-DAY volume is structurally wrong).

Deliberately independent of ID-5B's still-open current-session
provisional/off-grid M5 question: only canonical completed M5 bars ever
contribute to either the numerator or any denominator session — an
off-grid or still-forming row can never enter this contract. When
current-session canonical coverage disappears after the real production
drift onset, this contract honestly reports unavailable rather than
pretending a number exists.

No BUY/SELL, no probability, no HIGH_RVOL/LOW_RVOL/SURGE label — only a
zero-threshold sign-of-ratio relation (`RelativeVolumeRelation`) at the
1.0 (baseline) boundary. No config value/threshold is introduced by this
contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum, unique


@unique
class RelativeVolumeRelation(str, Enum):
    """Zero-threshold sign-of-`rvol_ratio` relation at the 1.0 boundary —
    no 1.2x/1.5x/2x band. Presentation-layer/EM-internal RVOL conventions
    elsewhere are NOT imported into this analytical contract."""

    ABOVE_BASELINE = "ABOVE_BASELINE"
    BELOW_BASELINE = "BELOW_BASELINE"
    AT_BASELINE = "AT_BASELINE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class RelativeVolumeContext:
    """Point-in-time cumulative-same-time relative volume evidence for one
    instrument — NOT a scoring input, NOT a Decision gate, NOT fused with
    ORB/Gap/RelativeStrength. `baseline_session_dates` makes the
    denominator fully reproducible — never an opaque ratio with no
    provenance. `available=False` whenever either side of the comparison
    cannot be honestly computed (no canonical current-session bars yet, no
    comparable historical session, or a zero historical average) —
    UNKNOWN is never substituted with a fabricated ratio."""

    instrument_id: str
    session_date: date
    as_of: datetime

    comparison_start_ts: datetime | None
    comparison_cutoff_ts: datetime | None
    current_cumulative_volume: int | None
    current_canonical_bar_count: int

    historical_average_cumulative_volume: Decimal | None
    baseline_session_count: int
    baseline_session_dates: tuple[date, ...]

    rvol_ratio: Decimal | None
    relation: RelativeVolumeRelation
    available: bool

    explanation: str

    def __post_init__(self) -> None:
        if not self.instrument_id:
            raise ValueError("RelativeVolumeContext.instrument_id is mandatory")
        if self.as_of.tzinfo is None:
            raise ValueError("RelativeVolumeContext.as_of must be timezone-aware")
        if not self.explanation:
            raise ValueError("RelativeVolumeContext.explanation is mandatory (ADR-005)")
