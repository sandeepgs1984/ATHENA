"""MP-NX2 display-only snapshot diff predicates."""

from __future__ import annotations

from decimal import Decimal

from athena.portfolio.snapshot_diff import SnapshotCompareRow, diff_snapshot_rows


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


def test_unchanged_rows_have_no_badges() -> None:
    row = _row()
    changes = diff_snapshot_rows((row,), (row,))
    assert len(changes) == 1
    assert changes[0].presence == "UNCHANGED"
    assert changes[0].badges == ()
    assert changes[0].fields == ()


def test_status_action_and_daily_review_changes_are_factual() -> None:
    previous = _row()
    current = _row(status="AT_RISK", next_action="EXIT", daily_review_status="REVIEW_HOLD_TIGHT")
    change = diff_snapshot_rows((previous,), (current,))[0]
    assert change.presence == "CHANGED"
    assert "Status changed" in change.badges
    assert "Action changed" in change.badges
    assert "Daily Review changed" in change.badges


def test_trend_flip_is_only_uptrend_versus_downtrend() -> None:
    flipped = diff_snapshot_rows(
        (_row(trend_setup="UPTREND / BREAKOUT"),),
        (_row(trend_setup="DOWNTREND / BREAKOUT"),),
    )[0]
    assert "Trend flipped" in flipped.badges
    mixed = diff_snapshot_rows(
        (_row(trend_setup="UPTREND / -"),),
        (_row(trend_setup="MIXED / -"),),
    )[0]
    assert "Trend changed" in mixed.badges
    assert "Trend flipped" not in mixed.badges


def test_pnl_moved_badge_uses_signed_delta() -> None:
    change = diff_snapshot_rows(
        (_row(pnl_pct=Decimal("4.0")),),
        (_row(pnl_pct=Decimal("8.2")),),
    )[0]
    assert "P&L moved +4.2%" in change.badges


def test_new_support_and_target_reached_use_existing_levels_only() -> None:
    previous = _row(support_1=None, last_price=Decimal("104"), plan_t1=Decimal("110"))
    current = _row(
        support_1="90-92",
        last_price=Decimal("111"),
        plan_t1=Decimal("110"),
    )
    change = diff_snapshot_rows((previous,), (current,))[0]
    assert "New support" in change.badges
    assert "Target reached" in change.badges


def test_added_and_removed_holdings_are_presence_only() -> None:
    kept = _row()
    added = _row(instrument_id="NSE:TCS", symbol="TCS")
    removed = _row(instrument_id="NSE:SBIN", symbol="SBIN")
    changes = {
        item.instrument_id: item
        for item in diff_snapshot_rows((kept, removed), (kept, added))
    }
    assert changes["NSE:TCS"].presence == "ADDED"
    assert changes["NSE:TCS"].badges == ("New holding",)
    assert changes["NSE:SBIN"].presence == "REMOVED"
    assert changes["NSE:SBIN"].badges == ("Removed holding",)
    assert changes["NSE:INFY"].presence == "UNCHANGED"
