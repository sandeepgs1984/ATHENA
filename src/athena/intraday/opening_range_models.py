"""Opening Range domain artifacts (ID-3).

Analytical evidence, NOT trade methodology: no BUY/SELL, no entry zone, no
stop/target, no confirmation/buffer rules, no STRONG/WEAK/FAILED labels.
Measures only. See `athena.intraday.opening_range_engine`.

Two parallel evidence windows, OR15 and OR30 — neither is treated as
canonically superior; that is a future validation question, not decided
here.

Pure, immutable, explainable (ADR-005): every artifact carries a mandatory,
non-empty explanation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum, unique


@unique
class OpeningRangeWindow(str, Enum):
    OR15 = "OR15"
    OR30 = "OR30"


@unique
class OpeningRangeFormationStatus(str, Enum):
    """Whether the range itself can be trusted as final. Only ``COMPLETE``
    means "use this high/low as the finished opening range" — the other
    four are all reasons not to, each objectively derived, never guessed."""

    #: The window's own time period has not fully elapsed yet at `as_of`.
    FORMING = "FORMING"
    #: The window's time has elapsed and every calendar-expected bar is present.
    COMPLETE = "COMPLETE"
    #: The window's time has elapsed but at least one expected bar is missing.
    INCOMPLETE_DATA = "INCOMPLETE_DATA"
    #: A real trading session, but its open/close is not notified (e.g. an
    #: unconfirmed Muhurat) -- expectations cannot be computed at all.
    NOT_AVAILABLE = "NOT_AVAILABLE"
    #: Not a trading session at all today.
    NOT_APPLICABLE = "NOT_APPLICABLE"


@unique
class OpeningRangeRelation(str, Enum):
    """Where the latest COMPLETED price sits relative to a COMPLETE range —
    a snapshot, not a transition. `UNAVAILABLE` whenever the range itself
    isn't COMPLETE yet, or no completed reference price exists."""

    ABOVE_RANGE = "ABOVE_RANGE"
    BELOW_RANGE = "BELOW_RANGE"
    INSIDE_RANGE = "INSIDE_RANGE"
    AT_HIGH = "AT_HIGH"
    AT_LOW = "AT_LOW"
    UNAVAILABLE = "UNAVAILABLE"


@unique
class BreakoutEvent(str, Enum):
    """A genuine, observed TRANSITION across a range boundary between two
    consecutive completed bars — distinct from `OpeningRangeRelation`
    (Section 7: being currently outside the range is not itself an event).
    Never inferred merely because price is already outside; requires an
    observed prior-inside-or-at-boundary bar followed by an outside one."""

    UPSIDE_BREAKOUT_EVENT = "UPSIDE_BREAKOUT_EVENT"
    DOWNSIDE_BREAKDOWN_EVENT = "DOWNSIDE_BREAKDOWN_EVENT"
    #: Checked (range COMPLETE, >=2 comparable bars); no transition found.
    NO_EVENT = "NO_EVENT"
    #: Cannot be checked -- range not COMPLETE, or fewer than 2 comparable
    #: completed bars exist (the range's own last bar plus at least one
    #: bar after it).
    NOT_OBSERVED = "NOT_OBSERVED"


@dataclass(frozen=True, slots=True)
class OpeningRangeFormation:
    """The range itself: boundaries, raw measurements, and whether it can
    be trusted as final yet. Reported whenever at least one constituent bar
    exists, regardless of `status` -- the status is what tells a consumer
    whether to treat it as final, not whether a value is present at all."""

    window: OpeningRangeWindow
    range_start: datetime | None
    range_end: datetime | None
    high: Decimal | None
    low: Decimal | None
    high_ts: datetime | None
    low_ts: datetime | None
    range_width: Decimal | None
    range_width_pct: Decimal | None
    volume: int | None
    bars_expected: int | None
    bars_present: int
    status: OpeningRangeFormationStatus
    explanation: str

    def __post_init__(self) -> None:
        if self.range_start is not None and self.range_start.tzinfo is None:
            raise ValueError("OpeningRangeFormation.range_start must be timezone-aware")
        if self.range_end is not None and self.range_end.tzinfo is None:
            raise ValueError("OpeningRangeFormation.range_end must be timezone-aware")
        if self.high_ts is not None and self.high_ts.tzinfo is None:
            raise ValueError("OpeningRangeFormation.high_ts must be timezone-aware")
        if self.low_ts is not None and self.low_ts.tzinfo is None:
            raise ValueError("OpeningRangeFormation.low_ts must be timezone-aware")
        if self.bars_present < 0:
            raise ValueError("OpeningRangeFormation.bars_present must be >= 0")
        if not self.explanation:
            raise ValueError("OpeningRangeFormation.explanation is mandatory (ADR-005)")


@dataclass(frozen=True, slots=True)
class OpeningRangeEvidence:
    """One window's (OR15 or OR30) complete evidence: formation, current
    relation, and post-formation breakout measurements. Measurements only —
    no STRONG/WEAK/FAILED label, no confirmation rule, no trade meaning."""

    instrument_id: str
    session_date: date
    as_of: datetime
    formation: OpeningRangeFormation
    relation: OpeningRangeRelation
    breakout_event: BreakoutEvent
    first_breakout_ts: datetime | None
    bars_since_breakout: int | None
    max_extension_from_range_pct: Decimal | None
    current_extension_pct: Decimal | None
    returned_inside_range: bool | None
    explanation: str

    def __post_init__(self) -> None:
        if not self.instrument_id:
            raise ValueError("OpeningRangeEvidence.instrument_id is mandatory")
        if self.as_of.tzinfo is None:
            raise ValueError("OpeningRangeEvidence.as_of must be timezone-aware")
        if self.first_breakout_ts is not None and self.first_breakout_ts.tzinfo is None:
            raise ValueError("OpeningRangeEvidence.first_breakout_ts must be timezone-aware")
        if self.bars_since_breakout is not None and self.bars_since_breakout < 0:
            raise ValueError("OpeningRangeEvidence.bars_since_breakout must be >= 0")
        if not self.explanation:
            raise ValueError("OpeningRangeEvidence.explanation is mandatory (ADR-005)")
