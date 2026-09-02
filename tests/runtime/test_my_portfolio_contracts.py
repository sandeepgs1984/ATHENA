"""PS-P1 My Portfolio contract tests."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from athena.portfolio.my_portfolio_contracts import (
    PORTFOLIO_ANALYSIS_VERSION,
    CanonicalPortfolioHolding,
    ImportedHoldingRow,
    PortfolioAnalysisProvenance,
    PortfolioFreshness,
    PortfolioSnapshotRow,
    PortfolioSnapshotSummary,
    ReconciliationAction,
    ResolvedImportedHoldingRow,
    SymbolMappingState,
    SyncRunStatus,
    calculate_portfolio_row_math,
    reconcile_current_holdings,
)

NOW = datetime(2026, 9, 2, 10, 0, tzinfo=timezone.utc)


def _holding(
    instrument_id: str,
    *,
    quantity: int = 10,
    avg_price: Decimal = Decimal("100"),
    source_row_id: str = "1",
) -> CanonicalPortfolioHolding:
    return CanonicalPortfolioHolding(
        instrument_id=instrument_id,
        quantity=quantity,
        avg_price=avg_price,
        imported_at=NOW,
        updated_at=NOW,
        source_import_id="imp-1",
        source_row_id=source_row_id,
    )


def test_imported_holding_row_validates_required_normalized_facts() -> None:
    row = ImportedHoldingRow(
        source_row_id="row-1",
        raw_symbol="INFY",
        quantity=5,
        avg_price=Decimal("1500.50"),
        holdings_as_of=NOW,
    )

    assert row.raw_symbol == "INFY"
    assert row.quantity == 5

    with pytest.raises(ValueError, match="quantity"):
        ImportedHoldingRow(
            source_row_id="row-2",
            raw_symbol="INFY",
            quantity=0,
            avg_price=Decimal("1500.50"),
        )


def test_symbol_mapping_states_guard_canonical_identity() -> None:
    imported = ImportedHoldingRow(
        source_row_id="row-1",
        raw_symbol="INFY",
        quantity=5,
        avg_price=Decimal("1500.50"),
    )

    resolved = ResolvedImportedHoldingRow(
        imported=imported,
        mapping_state=SymbolMappingState.RESOLVED,
        normalized_symbol="INFY",
        instrument_id="NSE:INFY",
    )
    assert resolved.instrument_id == "NSE:INFY"

    unresolved = ResolvedImportedHoldingRow(
        imported=imported,
        mapping_state=SymbolMappingState.UNRESOLVED,
        normalized_symbol="MISSING",
        errors=("symbol not found",),
    )
    assert unresolved.instrument_id is None

    with pytest.raises(ValueError, match="require instrument_id"):
        ResolvedImportedHoldingRow(
            imported=imported,
            mapping_state=SymbolMappingState.RESOLVED,
            normalized_symbol="INFY",
        )

    with pytest.raises(ValueError, match="must not carry instrument_id"):
        ResolvedImportedHoldingRow(
            imported=imported,
            mapping_state=SymbolMappingState.AMBIGUOUS,
            normalized_symbol="ABC",
            instrument_id="NSE:ABC",
        )


def test_reconciliation_classifies_added_updated_removed_and_unchanged() -> None:
    existing = {
        "NSE:ADDED": _holding("NSE:ADDED"),
        "NSE:REMOVED": _holding("NSE:REMOVED"),
        "NSE:UPDATED": _holding("NSE:UPDATED", quantity=10, avg_price=Decimal("100")),
        "NSE:UNCHANGED": _holding("NSE:UNCHANGED", quantity=7, avg_price=Decimal("80")),
    }
    uploaded = {
        "NSE:ADDED": _holding("NSE:ADDED"),
        "NSE:UPDATED": _holding("NSE:UPDATED", quantity=11, avg_price=Decimal("99")),
        "NSE:UNCHANGED": _holding("NSE:UNCHANGED", quantity=7, avg_price=Decimal("80")),
        "NSE:NEW": _holding("NSE:NEW"),
    }

    changes = reconcile_current_holdings(existing, uploaded)
    by_id = {change.instrument_id: change.action for change in changes}

    assert by_id == {
        "NSE:ADDED": ReconciliationAction.UNCHANGED,
        "NSE:NEW": ReconciliationAction.ADDED,
        "NSE:REMOVED": ReconciliationAction.REMOVED,
        "NSE:UNCHANGED": ReconciliationAction.UNCHANGED,
        "NSE:UPDATED": ReconciliationAction.UPDATED,
    }


def test_preview_reconciliation_does_not_mutate_holdings() -> None:
    existing_holding = _holding("NSE:INFY", quantity=10)
    existing = {"NSE:INFY": existing_holding}
    uploaded = {"NSE:INFY": _holding("NSE:INFY", quantity=8)}

    changes = reconcile_current_holdings(existing, uploaded)

    assert changes[0].action is ReconciliationAction.UPDATED
    assert existing["NSE:INFY"] is existing_holding
    assert existing["NSE:INFY"].quantity == 10


def test_server_side_portfolio_math_handles_available_and_absent_prices() -> None:
    math = calculate_portfolio_row_math(
        quantity=10,
        avg_price=Decimal("100"),
        last_price=Decimal("125"),
    )
    assert math.investment == Decimal("1000")
    assert math.current_value == Decimal("1250")
    assert math.pnl == Decimal("250")
    assert math.pnl_pct == Decimal("25.00")

    unavailable = calculate_portfolio_row_math(
        quantity=10,
        avg_price=Decimal("100"),
        last_price=None,
    )
    assert unavailable.investment == Decimal("1000")
    assert unavailable.current_value is None
    assert unavailable.pnl is None
    assert unavailable.pnl_pct is None


def test_complete_snapshot_row_preserves_nullable_methodology_fields() -> None:
    freshness = PortfolioFreshness(
        portfolio_imported_at=NOW,
        holdings_as_of=NOW,
        last_synced_at=NOW,
        market_data_through=NOW,
        analysis_version=PORTFOLIO_ANALYSIS_VERSION,
        decision_as_of=None,
        price_as_of=NOW,
    )
    provenance = PortfolioAnalysisProvenance(
        instrument_id="NSE:INFY",
        price_source="quotes",
        unavailable_fields=("status", "target_2", "target_3"),
    )

    row = PortfolioSnapshotRow.from_holding(
        symbol="INFY",
        holding=_holding("NSE:INFY", quantity=2, avg_price=Decimal("1500")),
        last_price=Decimal("1600"),
        price_as_of=NOW,
        freshness=freshness,
        provenance=provenance,
        target_1=Decimal("1700"),
    )

    assert row.symbol == "INFY"
    assert row.investment == Decimal("3000")
    assert row.current_value == Decimal("3200")
    assert row.status is None
    assert row.conviction is None
    assert row.target_1 == Decimal("1700")
    assert row.target_2 is None
    assert row.target_3 is None
    assert row.provenance.unavailable_fields == ("status", "target_2", "target_3")


def test_snapshot_summary_uses_server_owned_totals_and_partial_nulls() -> None:
    freshness = PortfolioFreshness(
        portfolio_imported_at=NOW,
        holdings_as_of=NOW,
        last_synced_at=NOW,
        market_data_through=NOW,
        analysis_version=PORTFOLIO_ANALYSIS_VERSION,
        decision_as_of=NOW,
        price_as_of=NOW,
    )
    provenance = PortfolioAnalysisProvenance(instrument_id="NSE:INFY")
    rows = (
        PortfolioSnapshotRow.from_holding(
            symbol="INFY",
            holding=_holding("NSE:INFY", quantity=1, avg_price=Decimal("100")),
            last_price=Decimal("110"),
            price_as_of=NOW,
            freshness=freshness,
            provenance=provenance,
        ),
    )

    summary = PortfolioSnapshotSummary.from_rows(
        rows,
        imported_at=NOW,
        holdings_as_of=NOW,
        last_synced_at=NOW,
        market_data_through=NOW,
        sync_status=SyncRunStatus.SUCCESS,
    )

    assert summary.holding_count == 1
    assert summary.total_investment == Decimal("100")
    assert summary.total_current_value == Decimal("110")
    assert summary.total_pnl == Decimal("10")
    assert summary.total_pnl_pct == Decimal("10.0")
    assert summary.sync_status is SyncRunStatus.SUCCESS
