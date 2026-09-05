"""PS-P1 My Portfolio API DTO contract tests."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from athena.api.v1.dtos.portfolio import (
    ImportedHoldingRowDTO,
    PortfolioAnalysisProvenanceDTO,
    PortfolioDailyReviewDTO,
    PortfolioFreshnessDTO,
    PortfolioImportPreviewDTO,
    PortfolioSnapshotDTO,
    PortfolioSnapshotRowDTO,
    PortfolioSnapshotSummaryDTO,
    PortfolioSyncRunDTO,
)
from athena.portfolio.my_portfolio_contracts import (
    ImportStatus,
    ReconciliationAction,
    SymbolMappingState,
    SyncRunStatus,
)

NOW = datetime(2026, 9, 2, 10, 0, tzinfo=timezone.utc)


def _freshness() -> PortfolioFreshnessDTO:
    return PortfolioFreshnessDTO(
        portfolio_imported_at=NOW,
        holdings_as_of=NOW,
        last_synced_at=NOW,
        market_data_through=NOW,
        analysis_version="my-portfolio-v1",
        decision_as_of=None,
        price_as_of=NOW,
    )


def test_import_preview_dto_exposes_mapping_failures_and_changes() -> None:
    preview = PortfolioImportPreviewDTO(
        import_id="imp-1",
        status=ImportStatus.PREVIEWED,
        total_rows=2,
        accepted_rows=1,
        rejected_rows=0,
        unresolved_rows=1,
        ambiguous_rows=0,
        warnings=["one unresolved symbol"],
        rows=[
            ImportedHoldingRowDTO(
                source_row_id="1",
                raw_symbol="INFY",
                normalized_symbol="INFY",
                quantity=10,
                avg_price=Decimal("1500"),
                mapping_state=SymbolMappingState.RESOLVED,
                resolved_instrument_id="NSE:INFY",
            ),
            ImportedHoldingRowDTO(
                source_row_id="2",
                raw_symbol="UNKNOWN",
                normalized_symbol="UNKNOWN",
                mapping_state=SymbolMappingState.UNRESOLVED,
                validation_errors=["symbol unresolved"],
            ),
        ],
        proposed_changes=[
            {
                "instrument_id": "NSE:INFY",
                "action": ReconciliationAction.ADDED,
                "before": None,
                "after": {"quantity": 10, "avg_price": "1500"},
            }
        ],
    )

    assert preview.rows[1].mapping_state is SymbolMappingState.UNRESOLVED
    assert preview.proposed_changes[0].action is ReconciliationAction.ADDED


def test_snapshot_row_dto_serializes_all_20_columns_and_nullable_fields() -> None:
    row = PortfolioSnapshotRowDTO(
        symbol="INFY",
        quantity=10,
        avg_price=Decimal("1500"),
        last_price=Decimal("1600"),
        price_as_of=NOW,
        investment=Decimal("15000"),
        current_value=Decimal("16000"),
        pnl=Decimal("1000"),
        pnl_pct=Decimal("6.6666666667"),
        status=None,
        conviction=None,
        trend_setup="UPTREND",
        key_trigger=None,
        support_1=None,
        major_support_exit=Decimal("1420"),
        target_1=Decimal("1700"),
        target_2=None,
        target_3=None,
        next_action=None,
        daily_review=PortfolioDailyReviewDTO(
            review_status="HOLD",
            methodology_version="portfolio-daily-review-v0",
            as_of=NOW,
            evidence_as_of=NOW,
            reason_codes=["BULLISH_TRAILING_STRUCTURE_INTACT"],
            guidance="Hold while SuperTrend trailing structure remains intact; targets deferred.",
            supertrend_direction="BULLISH",
            supertrend_value=Decimal("1420"),
            supertrend_version="supertrend-10-3-athena-v0",
            rsi14=Decimal("65"),
            volume=1000,
            volume_ma20=Decimal("900"),
            trailing_structure_level=Decimal("1420"),
        ),
        last_review=NOW,
        freshness=_freshness(),
        provenance=PortfolioAnalysisProvenanceDTO(
            instrument_id="NSE:INFY",
            decision_id="dec-1",
            unavailable_fields=["status", "target_2", "target_3"],
            daily_review_version="portfolio-daily-review-v0",
            daily_review_reason_codes=["BULLISH_TRAILING_STRUCTURE_INTACT"],
        ),
    )

    serialized = row.model_dump(by_alias=True)

    for field in (
        "symbol",
        "qty",
        "avg_price",
        "last_price",
        "price_as_of",
        "investment",
        "current_value",
        "pnl",
        "pnl_pct",
        "status",
        "conviction",
        "trend_or_setup",
        "key_trigger",
        "support_1",
        "major_support_exit",
        "target_1",
        "target_2",
        "target_3",
        "next_action",
        "daily_review",
        "last_review",
    ):
        assert field in serialized
    assert serialized["status"] is None
    assert serialized["target_2"] is None
    assert serialized["daily_review"]["review_status"] == "HOLD"
    assert serialized["provenance"]["daily_review_version"] == "portfolio-daily-review-v0"


def test_snapshot_summary_and_sync_status_contract_support_partial_success() -> None:
    sync = PortfolioSyncRunDTO(
        sync_run_id="sync-1",
        status=SyncRunStatus.PARTIAL,
        started_at=NOW,
        finished_at=NOW,
        total_holdings=3,
        succeeded_holdings=2,
        failed_holdings=1,
        market_data_through=NOW,
        validation_run_id="run-1",
        analysis_version="my-portfolio-v1",
        per_symbol={"NSE:BAD": {"status": "FAILED"}},
    )
    snapshot = PortfolioSnapshotDTO(
        snapshot_id="snap-1",
        generated_at=NOW,
        summary=PortfolioSnapshotSummaryDTO(
            holding_count=2,
            total_investment=Decimal("2000"),
            total_current_value=Decimal("2100"),
            total_pnl=Decimal("100"),
            total_pnl_pct=Decimal("5"),
            imported_at=NOW,
            holdings_as_of=NOW,
            last_synced_at=NOW,
            market_data_through=NOW,
            sync_status=SyncRunStatus.PARTIAL,
        ),
        rows=[],
    )

    assert sync.status is SyncRunStatus.PARTIAL
    assert sync.failed_holdings == 1
    assert snapshot.summary.sync_status is SyncRunStatus.PARTIAL
