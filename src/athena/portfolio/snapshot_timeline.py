"""Display-only review timeline from prior My Portfolio snapshots (MP-NX5).

Walks already-computed snapshot rows with the existing snapshot_diff fields.
Does not invent methodology, thresholds, ranking, or NX2 badge semantics.
Last Price is added here only so NX2 latest-vs-previous badges stay unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from athena.portfolio.snapshot_diff import (
    SnapshotCompareRow,
    SnapshotFieldChange,
    _format_decimal,
    _text,
    _values_equal,
    diff_snapshot_rows,
)


@dataclass(frozen=True)
class TimelineSnapshotPoint:
    """One completed snapshot run and this holding's row, if present."""

    snapshot_id: str
    generated_at: datetime | None
    sync_status: str
    row: SnapshotCompareRow | None


@dataclass(frozen=True)
class SnapshotTimelineEvent:
    """One factual older→newer comparison for a single holding."""

    snapshot_id: str
    previous_snapshot_id: str
    generated_at: datetime | None
    sync_status: str
    presence: str
    badges: tuple[str, ...]
    fields: tuple[SnapshotFieldChange, ...]


def _last_price_field(
    previous: SnapshotCompareRow,
    current: SnapshotCompareRow,
) -> SnapshotFieldChange | None:
    if _values_equal(previous.last_price, current.last_price):
        return None
    old = (
        _format_decimal(previous.last_price)
        if isinstance(previous.last_price, Decimal)
        else _text(previous.last_price)
    )
    new = (
        _format_decimal(current.last_price)
        if isinstance(current.last_price, Decimal)
        else _text(current.last_price)
    )
    return SnapshotFieldChange("last_price", "Last Price", old, new)


def build_symbol_timeline(
    points: tuple[TimelineSnapshotPoint, ...] | list[TimelineSnapshotPoint],
) -> tuple[SnapshotTimelineEvent, ...]:
    """Return newest-first events for consecutive snapshot pairs.

    UNCHANGED pairs with no Last Price delta are omitted so the overlay
    answers "what changed" rather than repeating every sync.
    """

    ordered = tuple(points)
    events: list[SnapshotTimelineEvent] = []
    for index in range(1, len(ordered)):
        previous = ordered[index - 1]
        current = ordered[index]
        if previous.row is None and current.row is None:
            continue
        if previous.row is None and current.row is not None:
            change = diff_snapshot_rows((), (current.row,))[0]
            events.append(
                SnapshotTimelineEvent(
                    snapshot_id=current.snapshot_id,
                    previous_snapshot_id=previous.snapshot_id,
                    generated_at=current.generated_at,
                    sync_status=current.sync_status,
                    presence=change.presence,
                    badges=change.badges,
                    fields=change.fields,
                )
            )
            continue
        if current.row is None and previous.row is not None:
            change = diff_snapshot_rows((previous.row,), ())[0]
            events.append(
                SnapshotTimelineEvent(
                    snapshot_id=current.snapshot_id,
                    previous_snapshot_id=previous.snapshot_id,
                    generated_at=current.generated_at,
                    sync_status=current.sync_status,
                    presence=change.presence,
                    badges=change.badges,
                    fields=change.fields,
                )
            )
            continue
        if previous.row is None or current.row is None:
            continue
        change = diff_snapshot_rows((previous.row,), (current.row,))[0]
        extra = _last_price_field(previous.row, current.row)
        fields = change.fields + ((extra,) if extra is not None else ())
        if not fields:
            continue
        events.append(
            SnapshotTimelineEvent(
                snapshot_id=current.snapshot_id,
                previous_snapshot_id=previous.snapshot_id,
                generated_at=current.generated_at,
                sync_status=current.sync_status,
                presence="CHANGED",
                badges=change.badges,
                fields=fields,
            )
        )
    return tuple(reversed(events))
