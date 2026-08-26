"""EM-1b chronological partition contract -- Owner/Chief Architect decision,
2026-08-26. Frozen unless changed later through an explicit Owner/Chief
Architect decision (per that approval's own closing line).

Strictly chronological, contiguous, non-overlapping, whole-session
assignment: TRAIN -> VALIDATION -> CALIBRATION -> FINAL_TEST. A trading
session's date alone determines its partition; every observation
(every symbol, every checkpoint, every event family/threshold) computed
for that session date always resolves to the same partition -- there is
no per-row or per-symbol randomness anywhere in this module.

FINAL_TEST is a sealed holdout per the approval: dataset-integrity checks
(row counts, partition membership, replay verification) may inspect it
freely; model-performance results may not be used for any development
decision before the approved final evaluation gate.

This module is pure: no I/O, no provider imports, no persistence. It
only classifies a session date into a partition role.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum
from itertools import pairwise

PARTITION_CONTRACT_VERSION = "em1b-partition-v1"


class PartitionRole(str, Enum):
    TRAIN = "TRAIN"
    VALIDATION = "VALIDATION"
    CALIBRATION = "CALIBRATION"
    FINAL_TEST = "FINAL_TEST"


@dataclass(frozen=True, slots=True)
class PartitionBoundary:
    """Inclusive [start_date, end_date] range for one partition role."""

    role: PartitionRole
    start_date: date
    end_date: date

    def __post_init__(self) -> None:
        if self.end_date < self.start_date:
            raise ValueError(f"{self.role.value}: end_date before start_date")


def _validated(boundaries: tuple[PartitionBoundary, ...]) -> tuple[PartitionBoundary, ...]:
    if not boundaries:
        raise ValueError("partition contract must declare at least one boundary")
    for previous, current in pairwise(boundaries):
        if current.start_date <= previous.end_date:
            raise ValueError(
                f"partition boundaries must be strictly chronological and "
                f"non-overlapping: {previous.role.value} ends "
                f"{previous.end_date}, {current.role.value} starts "
                f"{current.start_date}"
            )
        if current.start_date != previous.end_date + timedelta(days=1):
            raise ValueError(
                f"partition boundaries must be contiguous with no gap: "
                f"{previous.role.value} ends {previous.end_date}, "
                f"{current.role.value} starts {current.start_date}"
            )
    return boundaries


# Owner/Chief Architect approval, 2026-08-26 -- the exact EM-1b Chronological
# Partition Proposal, backed by real measured eligible-observation and
# positive-event distributions across the frozen study window (see
# artifacts/research/em1b/partition_measurement.json and the approved
# proposal in the milestone record). 743 real trading sessions total.
PARTITION_BOUNDARIES: tuple[PartitionBoundary, ...] = _validated((
    PartitionBoundary(PartitionRole.TRAIN, date(2023, 8, 14), date(2025, 5, 31)),
    PartitionBoundary(PartitionRole.VALIDATION, date(2025, 6, 1), date(2025, 9, 30)),
    PartitionBoundary(PartitionRole.CALIBRATION, date(2025, 10, 1), date(2025, 12, 31)),
    PartitionBoundary(PartitionRole.FINAL_TEST, date(2026, 1, 1), date(2026, 8, 21)),
))


def partition_for_session_date(session_date: date) -> PartitionRole:
    """The single partition role a trading session belongs to.

    Raises ValueError for any date outside the frozen contract's overall
    span -- there is no default/fallback partition; a date outside the
    contract is a caller error (the frozen study window), not a case this
    contract silently absorbs.
    """

    for boundary in PARTITION_BOUNDARIES:
        if boundary.start_date <= session_date <= boundary.end_date:
            return boundary.role
    raise ValueError(
        f"{session_date} falls outside the frozen EM-1b partition contract "
        f"({PARTITION_BOUNDARIES[0].start_date}..{PARTITION_BOUNDARIES[-1].end_date})"
    )
