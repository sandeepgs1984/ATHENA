"""Frozen EM research contracts and fail-closed dataset readiness checks.

This module deliberately contains no event-label calculation. EM-1a only freezes
the evidence requirements that later research must satisfy before labels exist.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum


class EventFamily(str, Enum):
    TOUCH = "TOUCH"
    CLOSE = "CLOSE"
    OPEN_TO_HIGH = "OPEN_TO_HIGH"


class ExclusionReason(str, Enum):
    CORPORATE_ACTION_COVERAGE_UNAVAILABLE = "CORPORATE_ACTION_COVERAGE_UNAVAILABLE"
    CORPORATE_ACTION_COVERAGE_INCOMPLETE = "CORPORATE_ACTION_COVERAGE_INCOMPLETE"
    UNADJUSTED_CORPORATE_ACTION_WINDOW = "UNADJUSTED_CORPORATE_ACTION_WINDOW"
    POINT_IN_TIME_MEMBERSHIP_UNAVAILABLE = "POINT_IN_TIME_MEMBERSHIP_UNAVAILABLE"
    NON_CANONICAL_INTRADAY_GRID = "NON_CANONICAL_INTRADAY_GRID"
    INCOMPLETE_INTRADAY_SESSION = "INCOMPLETE_INTRADAY_SESSION"


EVENT_FAMILIES: tuple[EventFamily, ...] = tuple(EventFamily)
EVENT_THRESHOLDS_PERCENT: tuple[int, ...] = (5, 8, 10, 12, 15, 20)
CANDIDATE_CHECKPOINTS_IST: tuple[str, ...] = (
    "09:20",
    "09:30",
    "09:45",
    "10:00",
    "10:30",
    "11:00",
    "12:00",
    "13:00",
    "14:00",
)


@dataclass(frozen=True, slots=True)
class CorporateActionCoverage:
    """Authoritative coverage period, distinct from the number of known actions."""

    authoritative_start: date | None
    authoritative_end: date | None
    action_count: int

    def __post_init__(self) -> None:
        if self.action_count < 0:
            raise ValueError("action_count cannot be negative")
        if (self.authoritative_start is None) != (self.authoritative_end is None):
            raise ValueError("authoritative coverage requires both start and end")
        if (
            self.authoritative_start is not None
            and self.authoritative_end is not None
            and self.authoritative_start > self.authoritative_end
        ):
            raise ValueError("authoritative_start cannot be after authoritative_end")

    def covers(self, start: date, end: date) -> bool:
        return bool(
            self.authoritative_start is not None
            and self.authoritative_end is not None
            and self.authoritative_start <= start
            and self.authoritative_end >= end
        )


@dataclass(frozen=True, slots=True)
class EventRecordReadiness:
    """Immutable decision about whether a research record may be emitted."""

    allowed: bool
    reasons: tuple[ExclusionReason, ...] = ()

    def __post_init__(self) -> None:
        if self.allowed == bool(self.reasons):
            raise ValueError("allowed records have no reasons; blocked records require reasons")


def assess_symbol_day_readiness(
    *,
    study_start: date,
    study_end: date,
    corporate_actions: CorporateActionCoverage,
    corporate_action_in_reference_window: bool,
    candles_fully_adjusted: bool,
    point_in_time_membership_available: bool,
) -> EventRecordReadiness:
    """Fail closed before a symbol-day can enter an EM research dataset."""

    if study_start > study_end:
        raise ValueError("study_start cannot be after study_end")

    reasons: list[ExclusionReason] = []
    if corporate_actions.authoritative_start is None:
        reasons.append(ExclusionReason.CORPORATE_ACTION_COVERAGE_UNAVAILABLE)
    elif not corporate_actions.covers(study_start, study_end):
        reasons.append(ExclusionReason.CORPORATE_ACTION_COVERAGE_INCOMPLETE)

    if corporate_action_in_reference_window and not candles_fully_adjusted:
        reasons.append(ExclusionReason.UNADJUSTED_CORPORATE_ACTION_WINDOW)

    if not point_in_time_membership_available:
        reasons.append(ExclusionReason.POINT_IN_TIME_MEMBERSHIP_UNAVAILABLE)

    return EventRecordReadiness(allowed=not reasons, reasons=tuple(reasons))


def assess_checkpoint_readiness(
    symbol_day: EventRecordReadiness,
    *,
    canonical_intraday_grid: bool,
    complete_intraday_session: bool,
) -> EventRecordReadiness:
    """Extend symbol-day readiness with checkpoint-specific evidence checks."""

    reasons = list(symbol_day.reasons)
    if not canonical_intraday_grid:
        reasons.append(ExclusionReason.NON_CANONICAL_INTRADAY_GRID)
    if not complete_intraday_session:
        reasons.append(ExclusionReason.INCOMPLETE_INTRADAY_SESSION)
    return EventRecordReadiness(allowed=not reasons, reasons=tuple(reasons))
