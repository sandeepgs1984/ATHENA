"""MP-NX5 display-only snapshot review timeline."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from athena.portfolio.snapshot_diff import SnapshotCompareRow
from athena.portfolio.snapshot_timeline import TimelineSnapshotPoint, build_symbol_timeline

FIRST = datetime(2026, 9, 6, 10, 0, tzinfo=timezone.utc)
SECOND = datetime(2026, 9, 7, 10, 0, tzinfo=timezone.utc)
THIRD = datetime(2026, 9, 8, 10, 0, tzinfo=timezone.utc)


def _row(**overrides: object) -> SnapshotCompareRow:
    payload = {
        "instrument_id": "NSE:INFY",
        "symbol": "INFY",
        "status": "HEALTHY",
        "daily_review_status": "HOLD",
        "next_action": "HOLD",
        "trend_setup": "UPTREND / -",
        "pnl_pct": Decimal("4.0"),
        "current_value": Decimal("1040"),
        "last_price": Decimal("104"),
        "plan_t1": Decimal("110"),
        "support_1": None,
        "structural_target_1": Decimal("112"),
        "daily_guidance": "Hold while structure remains intact.",
        "structural_guidance": None,
    }
    payload.update(overrides)
    return SnapshotCompareRow(**payload)  # type: ignore[arg-type]


def _point(
    snapshot_id: str,
    generated_at: datetime,
    row: SnapshotCompareRow | None,
    *,
    sync_status: str = "SUCCESS",
) -> TimelineSnapshotPoint:
    return TimelineSnapshotPoint(
        snapshot_id=snapshot_id,
        generated_at=generated_at,
        sync_status=sync_status,
        row=row,
    )


def test_one_snapshot_has_no_timeline_events() -> None:
    events = build_symbol_timeline((_point("sync-1", FIRST, _row()),))
    assert events == ()


def test_unchanged_pairs_are_omitted() -> None:
    row = _row()
    events = build_symbol_timeline(
        (
            _point("sync-1", FIRST, row),
            _point("sync-2", SECOND, row),
        )
    )
    assert events == ()


def test_status_and_action_changes_are_newest_first() -> None:
    events = build_symbol_timeline(
        (
            _point("sync-1", FIRST, _row()),
            _point("sync-2", SECOND, _row(status="AT_RISK", next_action="EXIT")),
            _point("sync-3", THIRD, _row(status="AT_RISK", next_action="WATCH")),
        )
    )
    assert [event.snapshot_id for event in events] == ["sync-3", "sync-2"]
    assert events[0].previous_snapshot_id == "sync-2"
    assert "Action changed" in events[0].badges
    assert "Status changed" in events[1].badges
    assert "Action changed" in events[1].badges


def test_last_price_change_is_timeline_only() -> None:
    events = build_symbol_timeline(
        (
            _point("sync-1", FIRST, _row(last_price=Decimal("104"))),
            _point("sync-2", SECOND, _row(last_price=Decimal("108"))),
        )
    )
    assert len(events) == 1
    assert events[0].presence == "CHANGED"
    assert events[0].fields[0].field_id == "last_price"
    assert events[0].fields[0].previous == "104"
    assert events[0].fields[0].current == "108"
    assert events[0].badges == ()


def test_partial_sync_status_is_preserved() -> None:
    events = build_symbol_timeline(
        (
            _point("sync-1", FIRST, _row()),
            _point(
                "sync-2",
                SECOND,
                _row(daily_guidance="Hold tighter while structure remains intact."),
                sync_status="PARTIAL",
            ),
        )
    )
    assert len(events) == 1
    assert events[0].sync_status == "PARTIAL"
    assert events[0].fields[0].field_id == "daily_guidance"


def test_added_and_removed_presence_events() -> None:
    events = build_symbol_timeline(
        (
            _point("sync-1", FIRST, None),
            _point("sync-2", SECOND, _row()),
            _point("sync-3", THIRD, None),
        )
    )
    assert [event.presence for event in events] == ["REMOVED", "ADDED"]
    assert events[0].badges == ("Removed holding",)
    assert events[1].badges == ("New holding",)


def test_same_symbol_exchange_remap_is_changed_not_added() -> None:
    events = build_symbol_timeline(
        (
            _point("sync-1", FIRST, _row(instrument_id="NSE:HFCL", symbol="HFCL")),
            _point(
                "sync-2",
                SECOND,
                _row(instrument_id="BSE:HFCL", symbol="HFCL", status="AT_RISK"),
            ),
        )
    )
    assert len(events) == 1
    assert events[0].presence == "CHANGED"
    assert events[0].badges[0] == "Listing remapped"
    assert events[0].fields[0].previous == "NSE:HFCL"
    assert events[0].fields[0].current == "BSE:HFCL"
