"""Portfolio resource DTOs (P8.3)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from athena.portfolio.my_portfolio_contracts import (
    ImportStatus,
    PortfolioSnapshotCurrentness,
    ReconciliationAction,
    SymbolMappingState,
    SyncRunStatus,
)


class PositionDTO(BaseModel):
    """Composed DTO representing open or closed trading positions."""

    model_config = ConfigDict(frozen=True)

    position_id: str
    instrument_id: str
    opened_ts: datetime
    quantity: int
    avg_price: Decimal
    closed_ts: datetime | None = None
    meta: dict[str, object] = Field(default_factory=dict)


class PortfolioSummaryDTO(BaseModel):
    """Composed DTO containing aggregated metrics and exposures."""

    model_config = ConfigDict(frozen=True)

    ts: datetime
    cash: Decimal
    exposure_by_sector: dict[str, Decimal]


class PortfolioDTO(BaseModel):
    """Composed DTO representing current balance sheet and open positions."""

    model_config = ConfigDict(frozen=True)

    summary: PortfolioSummaryDTO
    positions: list[PositionDTO]


class OpenPositionRequest(BaseModel):
    """Owner-entered open fill (manual log after Kite/Groww order)."""

    model_config = ConfigDict(frozen=True)

    instrument_id: str = Field(min_length=1, description="Stock symbol, e.g. INFY")
    quantity: int = Field(gt=0)
    avg_price: Decimal = Field(gt=0, description="Entry fill price")
    opened_ts: datetime | None = None
    decision_ref: str | None = None
    broker: str = Field(default="", description="kite | groww | other")
    notes: str = ""
    sector: str = ""


class ClosePositionRequest(BaseModel):
    """Owner-entered exit fill for an open position."""

    model_config = ConfigDict(frozen=True)

    exit_price: Decimal = Field(gt=0)
    closed_ts: datetime | None = None


class ResetPositionsRequest(BaseModel):
    """Destructive wipe of owner fill ledger rows (CONFIRM-gated)."""

    model_config = ConfigDict(frozen=True)

    confirmation: str = Field(description="Must be the exact token CONFIRM")
    scope: str = Field(description="open = open fills only; all = open + closed")


class ResetPositionsResultDTO(BaseModel):
    """Result of an owner fill ledger reset."""

    model_config = ConfigDict(frozen=True)

    scope: str
    deleted_count: int
    backup_path: str | None = None
    portfolio: PortfolioDTO


class ImportedHoldingRowDTO(BaseModel):
    """Normalized provider-independent holdings row after parsing."""

    model_config = ConfigDict(frozen=True)

    source_row_id: str
    raw_symbol: str
    normalized_symbol: str
    quantity: int | None = Field(default=None, gt=0)
    avg_price: Decimal | None = Field(default=None, gt=0)
    broker: str | None = None
    holdings_as_of: datetime | None = None
    source_metadata: dict[str, object] = Field(default_factory=dict)
    mapping_state: SymbolMappingState
    resolved_instrument_id: str | None = None
    candidates: list[dict[str, object]] = Field(default_factory=list)
    validation_errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class PortfolioReconciliationChangeDTO(BaseModel):
    """Preview/confirmation diff for one canonical instrument."""

    model_config = ConfigDict(frozen=True)

    instrument_id: str
    action: ReconciliationAction
    before: dict[str, object] | None = None
    after: dict[str, object] | None = None


class PortfolioImportPreviewDTO(BaseModel):
    """Import preview returned before canonical holdings mutate."""

    model_config = ConfigDict(frozen=True)

    import_id: str
    filename: str = ""
    source: str = "upload"
    status: ImportStatus
    total_rows: int = Field(ge=0)
    accepted_rows: int = Field(ge=0)
    rejected_rows: int = Field(ge=0)
    unresolved_rows: int = Field(ge=0)
    ambiguous_rows: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    rows: list[ImportedHoldingRowDTO]
    proposed_changes: list[PortfolioReconciliationChangeDTO]


class PortfolioImportConfirmRequest(BaseModel):
    """Confirm a previously previewed import/reconciliation."""

    model_config = ConfigDict(frozen=True)

    import_id: str
    confirmation: str = Field(description="Must be the exact token CONFIRM")


class MyPortfolioHoldingDTO(BaseModel):
    """Canonical current My Portfolio holding."""

    model_config = ConfigDict(frozen=True)

    instrument_id: str
    symbol: str
    quantity: int = Field(gt=0)
    avg_price: Decimal = Field(gt=0)
    investment: Decimal
    imported_at: datetime
    updated_at: datetime
    source_import_id: str
    source_row_id: str
    provenance: dict[str, object] = Field(default_factory=dict)


class PortfolioImportSummaryDTO(BaseModel):
    """Audit summary for a My Portfolio import batch."""

    model_config = ConfigDict(frozen=True)

    import_id: str
    filename: str
    source: str
    uploaded_at: datetime
    holdings_as_of: datetime | None = None
    parser_version: str
    status: ImportStatus
    total_rows: int = Field(ge=0)
    accepted_rows: int = Field(ge=0)
    rejected_rows: int = Field(ge=0)
    unresolved_rows: int = Field(ge=0)
    ambiguous_rows: int = Field(ge=0)
    confirmed_at: datetime | None = None
    provenance: dict[str, object] = Field(default_factory=dict)


class PortfolioImportConfirmResultDTO(BaseModel):
    """Result of confirming a persisted My Portfolio preview."""

    model_config = ConfigDict(frozen=True)

    import_id: str
    status: ImportStatus
    already_confirmed: bool
    holdings: list[MyPortfolioHoldingDTO]
    reconciliation: list[PortfolioReconciliationChangeDTO]


class PortfolioImportHistoryDTO(BaseModel):
    """Minimal My Portfolio import/reconciliation audit response."""

    model_config = ConfigDict(frozen=True)

    imports: list[PortfolioImportSummaryDTO]


class PortfolioFreshnessDTO(BaseModel):
    """Distinct freshness dimensions for My Portfolio analysis."""

    model_config = ConfigDict(frozen=True)

    portfolio_imported_at: datetime | None = None
    holdings_as_of: datetime | None = None
    last_synced_at: datetime | None = None
    market_data_through: datetime | None = None
    analysis_version: str
    decision_as_of: datetime | None = None
    price_as_of: datetime | None = None


class PortfolioAnalysisProvenanceDTO(BaseModel):
    """Persisted artifact references behind a snapshot row."""

    model_config = ConfigDict(frozen=True)

    instrument_id: str
    price_source: str | None = None
    candle_ref: str | None = None
    decision_id: str | None = None
    validation_run_id: str | None = None
    analyzed_at: datetime | None = None
    unavailable_fields: list[str] = Field(default_factory=list)
    failed_components: list[str] = Field(default_factory=list)
    interpretation_version: str | None = None
    interpretation_reason_codes: list[str] = Field(default_factory=list)
    interpretation_evidence: dict[str, object] = Field(default_factory=dict)
    daily_review_version: str | None = None
    daily_review_reason_codes: list[str] = Field(default_factory=list)
    daily_review_evidence: dict[str, object] = Field(default_factory=dict)


class PortfolioDailyReviewDTO(BaseModel):
    """Daily Chart Portfolio Review output for one holding."""

    model_config = ConfigDict(frozen=True)

    review_status: str | None = None
    methodology_version: str
    as_of: datetime | None = None
    evidence_as_of: datetime | None = None
    reason_codes: list[str] = Field(default_factory=list)
    guidance: str | None = None
    availability_reason: str | None = None
    supertrend_direction: str | None = None
    supertrend_value: Decimal | None = None
    supertrend_version: str
    rsi14: Decimal | None = None
    volume: int | None = None
    volume_ma20: Decimal | None = None
    available_history_high: Decimal | None = None
    latest_high_exceeds_prior_available_high: bool | None = None
    trailing_structure_level: Decimal | None = None


class PortfolioSnapshotRowDTO(BaseModel):
    """Complete My Portfolio Snapshot row with Daily Review extension."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    symbol: str
    quantity: int = Field(alias="qty", gt=0)
    avg_price: Decimal
    last_price: Decimal | None = None
    price_as_of: datetime | None = None
    investment: Decimal
    current_value: Decimal | None = None
    pnl: Decimal | None = None
    pnl_pct: Decimal | None = None
    status: str | None = None
    conviction: str | None = None
    trend_setup: str | None = Field(default=None, alias="trend_or_setup")
    key_trigger: str | None = None
    support_1: Decimal | None = None
    major_support_exit: Decimal | None = None
    target_1: Decimal | None = None
    target_2: Decimal | None = None
    target_3: Decimal | None = None
    next_action: str | None = None
    daily_review: PortfolioDailyReviewDTO | None = None
    last_review: datetime | None = None
    freshness: PortfolioFreshnessDTO
    provenance: PortfolioAnalysisProvenanceDTO


class PortfolioSnapshotSummaryDTO(BaseModel):
    """Server-owned My Portfolio header summary."""

    model_config = ConfigDict(frozen=True)

    holding_count: int = Field(ge=0)
    total_investment: Decimal
    total_current_value: Decimal | None = None
    total_pnl: Decimal | None = None
    total_pnl_pct: Decimal | None = None
    imported_at: datetime | None = None
    holdings_as_of: datetime | None = None
    last_synced_at: datetime | None = None
    market_data_through: datetime | None = None
    sync_status: SyncRunStatus | None = None


class PortfolioSnapshotDTO(BaseModel):
    """Latest completed My Portfolio Snapshot."""

    model_config = ConfigDict(frozen=True)

    snapshot_id: str
    generated_at: datetime
    currentness: PortfolioSnapshotCurrentness = PortfolioSnapshotCurrentness.UNKNOWN
    portfolio_changed_since_sync: bool = False
    currentness_reason: str | None = None
    snapshot_holdings_digest: str | None = None
    current_holdings_digest: str | None = None
    summary: PortfolioSnapshotSummaryDTO
    rows: list[PortfolioSnapshotRowDTO]


class PortfolioSyncStartRequest(BaseModel):
    """Start a background Portfolio Sync run."""

    model_config = ConfigDict(frozen=True)

    force_ingestion: bool = False


class PortfolioSyncRunDTO(BaseModel):
    """Background Portfolio Sync progress/result contract."""

    model_config = ConfigDict(frozen=True)

    sync_run_id: str
    status: SyncRunStatus
    started_at: datetime
    finished_at: datetime | None = None
    total_holdings: int = Field(ge=0)
    succeeded_holdings: int = Field(ge=0)
    failed_holdings: int = Field(ge=0)
    market_data_through: datetime | None = None
    validation_run_id: str | None = None
    analysis_version: str
    progress: dict[str, object] = Field(default_factory=dict)
    per_symbol: dict[str, object] = Field(default_factory=dict)
    error: dict[str, object] = Field(default_factory=dict)
