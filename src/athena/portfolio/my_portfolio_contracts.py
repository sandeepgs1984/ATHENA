"""My Portfolio contract objects for PS-P1.

These contracts intentionally stop at holdings import/reconciliation, snapshot
math, freshness, provenance, and sync state. They do not introduce portfolio
trading methodology or modify ATHENA's scoring/decision engines.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from types import MappingProxyType

PORTFOLIO_ANALYSIS_VERSION = "my-portfolio-v1"


class ImportStatus(str, Enum):
    """Lifecycle for an uploaded holdings import."""

    PREVIEWED = "PREVIEWED"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class SymbolMappingState(str, Enum):
    """Canonical symbol-resolution state for an imported row."""

    RESOLVED = "RESOLVED"
    UNRESOLVED = "UNRESOLVED"
    AMBIGUOUS = "AMBIGUOUS"


class ReconciliationAction(str, Enum):
    """Current-holdings snapshot reconciliation action."""

    ADDED = "ADDED"
    UPDATED = "UPDATED"
    REMOVED = "REMOVED"
    UNCHANGED = "UNCHANGED"


class SyncRunStatus(str, Enum):
    """Background Portfolio Sync run status."""

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class PortfolioSnapshotCurrentness(str, Enum):
    """Whether a snapshot reflects the current canonical holdings state."""

    CURRENT = "CURRENT"
    STALE_HOLDINGS_CHANGED = "STALE_HOLDINGS_CHANGED"
    NO_SNAPSHOT = "NO_SNAPSHOT"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class ImportedHoldingRow:
    """Provider-independent normalized row parsed from a holdings file."""

    source_row_id: str
    raw_symbol: str
    quantity: int
    avg_price: Decimal
    broker: str | None = None
    source_metadata: Mapping[str, object] = field(default_factory=dict)
    holdings_as_of: datetime | None = None

    def __post_init__(self) -> None:
        if not self.source_row_id:
            raise ValueError("ImportedHoldingRow.source_row_id is mandatory")
        if not self.raw_symbol.strip():
            raise ValueError("ImportedHoldingRow.raw_symbol is mandatory")
        if self.quantity <= 0:
            raise ValueError("ImportedHoldingRow.quantity must be > 0")
        if self.avg_price <= Decimal("0"):
            raise ValueError("ImportedHoldingRow.avg_price must be > 0")
        if self.holdings_as_of is not None and self.holdings_as_of.tzinfo is None:
            raise ValueError("ImportedHoldingRow.holdings_as_of must be timezone-aware")
        object.__setattr__(self, "source_metadata", MappingProxyType(dict(self.source_metadata)))


@dataclass(frozen=True, slots=True)
class ResolvedImportedHoldingRow:
    """Imported row after validation and canonical symbol resolution."""

    imported: ImportedHoldingRow
    mapping_state: SymbolMappingState
    normalized_symbol: str
    instrument_id: str | None = None
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.normalized_symbol:
            raise ValueError("ResolvedImportedHoldingRow.normalized_symbol is mandatory")
        if self.mapping_state is SymbolMappingState.RESOLVED and not self.instrument_id:
            raise ValueError("RESOLVED imported rows require instrument_id")
        if self.mapping_state is not SymbolMappingState.RESOLVED and self.instrument_id is not None:
            raise ValueError("unresolved/ambiguous rows must not carry instrument_id")


@dataclass(frozen=True, slots=True)
class CanonicalPortfolioHolding:
    """Canonical current My Portfolio holding: one row per instrument."""

    instrument_id: str
    quantity: int
    avg_price: Decimal
    imported_at: datetime
    updated_at: datetime
    source_import_id: str
    source_row_id: str
    provenance: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.instrument_id or ":" not in self.instrument_id:
            raise ValueError("CanonicalPortfolioHolding.instrument_id must be canonical")
        if self.quantity <= 0:
            raise ValueError("CanonicalPortfolioHolding.quantity must be > 0")
        if self.avg_price <= Decimal("0"):
            raise ValueError("CanonicalPortfolioHolding.avg_price must be > 0")
        if self.imported_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ValueError("CanonicalPortfolioHolding timestamps must be timezone-aware")
        if not self.source_import_id or not self.source_row_id:
            raise ValueError("CanonicalPortfolioHolding source provenance is mandatory")
        object.__setattr__(self, "provenance", MappingProxyType(dict(self.provenance)))


@dataclass(frozen=True, slots=True)
class ReconciliationChange:
    """Auditable before/after diff for one canonical instrument."""

    instrument_id: str
    action: ReconciliationAction
    before: CanonicalPortfolioHolding | None
    after: CanonicalPortfolioHolding | None


def reconcile_current_holdings(
    existing: Mapping[str, CanonicalPortfolioHolding],
    uploaded: Mapping[str, CanonicalPortfolioHolding],
) -> tuple[ReconciliationChange, ...]:
    """Build a deterministic current-holdings diff without inventing trades."""

    changes: list[ReconciliationChange] = []
    for instrument_id in sorted(set(existing) | set(uploaded)):
        before = existing.get(instrument_id)
        after = uploaded.get(instrument_id)
        if before is None and after is not None:
            action = ReconciliationAction.ADDED
        elif before is not None and after is None:
            action = ReconciliationAction.REMOVED
        elif before is not None and after is not None:
            if before.quantity == after.quantity and before.avg_price == after.avg_price:
                action = ReconciliationAction.UNCHANGED
            else:
                action = ReconciliationAction.UPDATED
        else:  # pragma: no cover - set union makes this unreachable.
            continue
        changes.append(
            ReconciliationChange(
                instrument_id=instrument_id,
                action=action,
                before=before,
                after=after,
            )
        )
    return tuple(changes)


@dataclass(frozen=True, slots=True)
class PortfolioRowMath:
    """Server-owned math for one Portfolio Snapshot row."""

    investment: Decimal
    current_value: Decimal | None
    pnl: Decimal | None
    pnl_pct: Decimal | None


def calculate_portfolio_row_math(
    *,
    quantity: int,
    avg_price: Decimal,
    last_price: Decimal | None,
) -> PortfolioRowMath:
    """Compute snapshot math while keeping invalid/absent marks explicit."""

    investment = Decimal(quantity) * avg_price
    if investment <= Decimal("0") or last_price is None:
        return PortfolioRowMath(
            investment=investment,
            current_value=None,
            pnl=None,
            pnl_pct=None,
        )
    current_value = Decimal(quantity) * last_price
    pnl = current_value - investment
    try:
        pnl_pct = (pnl / investment) * Decimal("100")
    except (InvalidOperation, ZeroDivisionError):
        pnl_pct = None
    return PortfolioRowMath(
        investment=investment,
        current_value=current_value,
        pnl=pnl,
        pnl_pct=pnl_pct,
    )


@dataclass(frozen=True, slots=True)
class PortfolioFreshness:
    """Distinct freshness dimensions for My Portfolio."""

    portfolio_imported_at: datetime | None
    holdings_as_of: datetime | None
    last_synced_at: datetime | None
    market_data_through: datetime | None
    analysis_version: str
    decision_as_of: datetime | None
    price_as_of: datetime | None


@dataclass(frozen=True, slots=True)
class PortfolioAnalysisProvenance:
    """References to the persisted ATHENA artifacts behind a snapshot row."""

    instrument_id: str
    price_source: str | None = None
    candle_ref: str | None = None
    decision_id: str | None = None
    validation_run_id: str | None = None
    analyzed_at: datetime | None = None
    unavailable_fields: tuple[str, ...] = ()
    failed_components: tuple[str, ...] = ()
    interpretation_version: str | None = None
    interpretation_reason_codes: tuple[str, ...] = ()
    interpretation_evidence: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PortfolioSnapshotRow:
    """Complete 20-column server-side Portfolio Snapshot row."""

    symbol: str
    quantity: int
    avg_price: Decimal
    last_price: Decimal | None
    price_as_of: datetime | None
    investment: Decimal
    current_value: Decimal | None
    pnl: Decimal | None
    pnl_pct: Decimal | None
    status: str | None
    conviction: str | None
    trend_setup: str | None
    key_trigger: str | None
    support_1: Decimal | None
    major_support_exit: Decimal | None
    target_1: Decimal | None
    target_2: Decimal | None
    target_3: Decimal | None
    next_action: str | None
    last_review: datetime | None
    freshness: PortfolioFreshness
    provenance: PortfolioAnalysisProvenance

    @classmethod
    def from_holding(
        cls,
        *,
        symbol: str,
        holding: CanonicalPortfolioHolding,
        last_price: Decimal | None,
        price_as_of: datetime | None,
        freshness: PortfolioFreshness,
        provenance: PortfolioAnalysisProvenance,
        status: str | None = None,
        conviction: str | None = None,
        trend_setup: str | None = None,
        key_trigger: str | None = None,
        support_1: Decimal | None = None,
        major_support_exit: Decimal | None = None,
        target_1: Decimal | None = None,
        target_2: Decimal | None = None,
        target_3: Decimal | None = None,
        next_action: str | None = None,
        last_review: datetime | None = None,
    ) -> PortfolioSnapshotRow:
        math = calculate_portfolio_row_math(
            quantity=holding.quantity,
            avg_price=holding.avg_price,
            last_price=last_price,
        )
        return cls(
            symbol=symbol,
            quantity=holding.quantity,
            avg_price=holding.avg_price,
            last_price=last_price,
            price_as_of=price_as_of,
            investment=math.investment,
            current_value=math.current_value,
            pnl=math.pnl,
            pnl_pct=math.pnl_pct,
            status=status,
            conviction=conviction,
            trend_setup=trend_setup,
            key_trigger=key_trigger,
            support_1=support_1,
            major_support_exit=major_support_exit,
            target_1=target_1,
            target_2=target_2,
            target_3=target_3,
            next_action=next_action,
            last_review=last_review,
            freshness=freshness,
            provenance=provenance,
        )


@dataclass(frozen=True, slots=True)
class PortfolioSnapshotSummary:
    """Server-owned My Portfolio header summary."""

    holding_count: int
    total_investment: Decimal
    total_current_value: Decimal | None
    total_pnl: Decimal | None
    total_pnl_pct: Decimal | None
    imported_at: datetime | None
    holdings_as_of: datetime | None
    last_synced_at: datetime | None
    market_data_through: datetime | None
    sync_status: SyncRunStatus | None

    @classmethod
    def from_rows(
        cls,
        rows: tuple[PortfolioSnapshotRow, ...],
        *,
        imported_at: datetime | None,
        holdings_as_of: datetime | None,
        last_synced_at: datetime | None,
        market_data_through: datetime | None,
        sync_status: SyncRunStatus | None,
    ) -> PortfolioSnapshotSummary:
        total_investment = sum((row.investment for row in rows), Decimal("0"))
        if any(row.current_value is None or row.pnl is None for row in rows):
            total_current_value = None
            total_pnl = None
            total_pnl_pct = None
        else:
            total_current_value = sum(
                (row.current_value for row in rows if row.current_value is not None),
                Decimal("0"),
            )
            total_pnl = sum((row.pnl for row in rows if row.pnl is not None), Decimal("0"))
            total_pnl_pct = (
                (total_pnl / total_investment) * Decimal("100")
                if total_investment > Decimal("0")
                else None
            )
        return cls(
            holding_count=len(rows),
            total_investment=total_investment,
            total_current_value=total_current_value,
            total_pnl=total_pnl,
            total_pnl_pct=total_pnl_pct,
            imported_at=imported_at,
            holdings_as_of=holdings_as_of,
            last_synced_at=last_synced_at,
            market_data_through=market_data_through,
            sync_status=sync_status,
        )
