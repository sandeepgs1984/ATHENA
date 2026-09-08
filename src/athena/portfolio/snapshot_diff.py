"""Display-only snapshot-to-snapshot diffs for My Portfolio (MP-NX2).

Compares already-computed snapshot fields. Does not invent methodology,
thresholds, or risk scores.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


def _text(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _decimal(value: object | None) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _trend_parts(trend_setup: object | None) -> tuple[str | None, str | None]:
    raw = _text(trend_setup)
    if raw is None:
        return None, None
    upper = raw.upper()
    trend = upper.split("/", 1)[0].strip() or None
    setup = upper.split("/", 1)[1].strip() if "/" in upper else None
    if setup in {None, "", "-"}:
        setup = None
    if trend == "-":
        trend = None
    return trend, setup


def _values_equal(left: object | None, right: object | None) -> bool:
    if left is None and right is None:
        return True
    left_decimal = _decimal(left) if not isinstance(left, str) or _decimal(left) is not None else None
    right_decimal = _decimal(right) if not isinstance(right, str) or _decimal(right) is not None else None
    if left_decimal is not None and right_decimal is not None and not isinstance(left, bool):
        return left_decimal == right_decimal
    return _text(left) == _text(right)


def _format_decimal(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value, "f")


def _format_signed_pct(delta: Decimal) -> str:
    quantized = delta.quantize(Decimal("0.1"))
    if quantized > 0:
        return f"+{quantized}%"
    return f"{quantized}%"


def _crossed_from_below(
    previous_price: Decimal | None,
    current_price: Decimal | None,
    level: Decimal | None,
) -> bool:
    if previous_price is None or current_price is None or level is None:
        return False
    return previous_price < level <= current_price


@dataclass(frozen=True)
class SnapshotCompareRow:
    """Minimal already-computed fields needed for a display diff."""

    instrument_id: str
    symbol: str
    status: str | None = None
    daily_review_status: str | None = None
    next_action: str | None = None
    trend_setup: str | None = None
    pnl_pct: Decimal | None = None
    current_value: Decimal | None = None
    last_price: Decimal | None = None
    plan_t1: Decimal | None = None
    support_1: str | None = None
    structural_target_1: Decimal | None = None
    daily_guidance: str | None = None
    structural_guidance: str | None = None


@dataclass(frozen=True)
class SnapshotFieldChange:
    field_id: str
    label: str
    previous: str | None
    current: str | None


@dataclass(frozen=True)
class SnapshotRowChange:
    instrument_id: str
    symbol: str
    presence: str
    badges: tuple[str, ...]
    fields: tuple[SnapshotFieldChange, ...]


def diff_snapshot_rows(
    previous_rows: tuple[SnapshotCompareRow, ...] | list[SnapshotCompareRow],
    current_rows: tuple[SnapshotCompareRow, ...] | list[SnapshotCompareRow],
) -> tuple[SnapshotRowChange, ...]:
    """Return factual per-row diffs. Presence is ADDED, REMOVED, CHANGED, or UNCHANGED."""

    previous_by_key = {row.instrument_id: row for row in previous_rows}
    current_by_key = {row.instrument_id: row for row in current_rows}
    changes: list[SnapshotRowChange] = []

    for key in sorted(set(previous_by_key) | set(current_by_key)):
        previous = previous_by_key.get(key)
        current = current_by_key.get(key)
        if previous is None and current is not None:
            changes.append(
                SnapshotRowChange(
                    instrument_id=current.instrument_id,
                    symbol=current.symbol,
                    presence="ADDED",
                    badges=("New holding",),
                    fields=(),
                )
            )
            continue
        if current is None and previous is not None:
            changes.append(
                SnapshotRowChange(
                    instrument_id=previous.instrument_id,
                    symbol=previous.symbol,
                    presence="REMOVED",
                    badges=("Removed holding",),
                    fields=(),
                )
            )
            continue
        if previous is None or current is None:
            continue
        fields, badges = _diff_pair(previous, current)
        changes.append(
            SnapshotRowChange(
                instrument_id=current.instrument_id,
                symbol=current.symbol,
                presence="CHANGED" if fields else "UNCHANGED",
                badges=badges,
                fields=fields,
            )
        )
    return _merge_same_symbol_remaps(tuple(changes), previous_by_key, current_by_key)


def _change_symbol(item: SnapshotRowChange) -> str:
    return (item.symbol or item.instrument_id.split(":", 1)[-1]).upper()


def _merge_same_symbol_remaps(
    changes: tuple[SnapshotRowChange, ...],
    previous_by_key: dict[str, SnapshotCompareRow],
    current_by_key: dict[str, SnapshotCompareRow],
) -> tuple[SnapshotRowChange, ...]:
    """Treat NSE→BSE (same tradingsymbol) as a listing change, not a remove.

    Snapshot rows are keyed by instrument_id. A remap leaves the old id
    absent and the new id present, which would otherwise look like a sale.
    """

    removed = [item for item in changes if item.presence == "REMOVED"]
    added = [item for item in changes if item.presence == "ADDED"]
    kept = [item for item in changes if item.presence not in {"REMOVED", "ADDED"}]
    removed_by_symbol: dict[str, list[SnapshotRowChange]] = {}
    added_by_symbol: dict[str, list[SnapshotRowChange]] = {}
    for item in removed:
        removed_by_symbol.setdefault(_change_symbol(item), []).append(item)
    for item in added:
        added_by_symbol.setdefault(_change_symbol(item), []).append(item)

    consumed: set[str] = set()
    remapped: list[SnapshotRowChange] = []
    for symbol, removed_items in removed_by_symbol.items():
        added_items = added_by_symbol.get(symbol, [])
        if len(removed_items) != 1 or len(added_items) != 1:
            continue
        previous = previous_by_key.get(removed_items[0].instrument_id)
        current = current_by_key.get(added_items[0].instrument_id)
        if previous is None or current is None:
            continue
        if previous.instrument_id == current.instrument_id:
            continue
        fields, badges = _diff_pair(previous, current)
        listing = SnapshotFieldChange(
            "instrument_id",
            "Listing",
            previous.instrument_id,
            current.instrument_id,
        )
        remapped.append(
            SnapshotRowChange(
                instrument_id=current.instrument_id,
                symbol=current.symbol,
                presence="CHANGED",
                badges=("Listing remapped",) + badges,
                fields=(listing,) + fields,
            )
        )
        consumed.add(removed_items[0].instrument_id)
        consumed.add(added_items[0].instrument_id)

    leftover = [
        item
        for item in (*removed, *added)
        if item.instrument_id not in consumed
    ]
    return tuple(sorted((*kept, *remapped, *leftover), key=lambda item: item.instrument_id))


def _diff_pair(
    previous: SnapshotCompareRow,
    current: SnapshotCompareRow,
) -> tuple[tuple[SnapshotFieldChange, ...], tuple[str, ...]]:
    fields: list[SnapshotFieldChange] = []
    badges: list[str] = []
    previous_trend, previous_setup = _trend_parts(previous.trend_setup)
    current_trend, current_setup = _trend_parts(current.trend_setup)

    comparisons = (
        ("status", "Status", previous.status, current.status, "Status changed"),
        (
            "daily_review_status",
            "Daily Review",
            previous.daily_review_status,
            current.daily_review_status,
            "Daily Review changed",
        ),
        ("next_action", "Next Action", previous.next_action, current.next_action, "Action changed"),
        ("trend", "Trend", previous_trend, current_trend, None),
        ("setup", "Setup", previous_setup, current_setup, "Setup changed"),
        ("pnl_pct", "P&L %", previous.pnl_pct, current.pnl_pct, None),
        ("current_value", "Current Value", previous.current_value, current.current_value, None),
        ("support_1", "Support 1", previous.support_1, current.support_1, None),
        (
            "daily_guidance",
            "Daily Guidance",
            previous.daily_guidance,
            current.daily_guidance,
            None,
        ),
        (
            "structural_guidance",
            "Structural Guidance",
            previous.structural_guidance,
            current.structural_guidance,
            None,
        ),
    )
    for field_id, label, old, new, badge in comparisons:
        if _values_equal(old, new):
            continue
        old_text = _format_decimal(old) if isinstance(old, Decimal) else _text(old)
        new_text = _format_decimal(new) if isinstance(new, Decimal) else _text(new)
        fields.append(SnapshotFieldChange(field_id, label, old_text, new_text))
        if badge:
            badges.append(badge)
        elif field_id == "trend":
            flipped = {previous_trend, current_trend} == {"UPTREND", "DOWNTREND"}
            badges.append("Trend flipped" if flipped else "Trend changed")
        elif field_id == "pnl_pct":
            previous_pct = _decimal(previous.pnl_pct)
            current_pct = _decimal(current.pnl_pct)
            if previous_pct is not None and current_pct is not None:
                badges.append(f"P&L moved {_format_signed_pct(current_pct - previous_pct)}")
        elif field_id == "support_1" and previous.support_1 in {None, ""} and current.support_1:
            badges.append("New support")

    if _crossed_from_below(previous.last_price, current.last_price, current.plan_t1) or (
        _crossed_from_below(previous.last_price, current.last_price, current.structural_target_1)
    ):
        badges.append("Target reached")
        fields.append(
            SnapshotFieldChange(
                "target_reached",
                "Target",
                _format_decimal(previous.last_price),
                _format_decimal(current.last_price),
            )
        )

    return tuple(fields), tuple(badges)
