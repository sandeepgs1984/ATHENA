"""My Portfolio import preview and reconciliation service (PS-P2)."""

from __future__ import annotations

import hashlib
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from athena.api.exceptions import (
    MyPortfolioImportError,
    MyPortfolioImportNotFoundError,
    StalePortfolioPreviewError,
)
from athena.api.v1.dtos.portfolio import (
    ImportedHoldingRowDTO,
    MyPortfolioHoldingDTO,
    PortfolioImportConfirmResultDTO,
    PortfolioImportHistoryDTO,
    PortfolioImportPreviewDTO,
    PortfolioImportSummaryDTO,
    PortfolioReconciliationChangeDTO,
)
from athena.data.store.repository import SqliteRepository
from athena.errors import RepositoryError
from athena.portfolio.imports import (
    ResolvedHoldingPreviewRow,
    build_symbol_resolver_index,
    parse_holdings_file,
    resolve_preview_rows,
)
from athena.portfolio.my_portfolio_contracts import (
    CanonicalPortfolioHolding,
    ImportStatus,
    ReconciliationAction,
    ReconciliationChange,
    SymbolMappingState,
    reconcile_current_holdings,
)

_CONFIRM_TOKEN = "CONFIRM"


class MyPortfolioService:
    """Coordinates My Portfolio import preview, confirmation, and audit reads."""

    def __init__(self, repo: SqliteRepository) -> None:
        self._repo = repo

    def preview_import(self, *, filename: str, content: bytes) -> PortfolioImportPreviewDTO:
        now = datetime.now(tz=timezone.utc)
        import_id = f"pimp-{uuid4().hex}"
        digest = hashlib.sha256(content).hexdigest()
        parsed = parse_holdings_file(filename, content)
        base_digest = self._repo.portfolio_holdings_digest()

        if parsed.is_valid_file:
            index = build_symbol_resolver_index(
                self._repo.list_symbol_records(),
                self._repo.list_instruments(),
            )
            rows = resolve_preview_rows(parsed.rows, index)
        else:
            rows = ()

        counts = self._counts(parsed.errors, rows)
        status = ImportStatus.PREVIEWED if parsed.is_valid_file else ImportStatus.FAILED

        self._repo.save_portfolio_import_preview(
            import_id=import_id,
            filename=filename,
            source="upload",
            uploaded_at=now,
            holdings_as_of=None,
            parser_version=parsed.parser_version,
            status=status,
            total_rows=counts["total_rows"],
            accepted_rows=counts["accepted_rows"],
            rejected_rows=counts["rejected_rows"],
            unresolved_rows=counts["unresolved_rows"],
            ambiguous_rows=counts["ambiguous_rows"],
            provenance={
                "file_sha256": digest,
                "base_holdings_digest": base_digest,
                "parser_warnings": list(parsed.warnings),
                "parser_errors": list(parsed.errors),
            },
            rows=[self._row_to_repository_dict(row) for row in rows],
        )
        return self.get_import_preview(import_id)

    def get_import_preview(self, import_id: str) -> PortfolioImportPreviewDTO:
        record = self._repo.get_portfolio_import(import_id)
        if record is None:
            raise MyPortfolioImportNotFoundError(f"portfolio import not found: {import_id}")
        rows = self._repo.list_portfolio_import_rows(import_id)
        changes = self._reconciliation_for_import(record, rows)
        provenance = dict(record["provenance"])
        return PortfolioImportPreviewDTO(
            import_id=str(record["import_id"]),
            filename=str(record["filename"]),
            source=str(record["source"]),
            status=ImportStatus(str(record["status"])),
            total_rows=int(record["total_rows"]),
            accepted_rows=int(record["accepted_rows"]),
            rejected_rows=int(record["rejected_rows"]),
            unresolved_rows=int(record["unresolved_rows"]),
            ambiguous_rows=int(record["ambiguous_rows"]),
            warnings=list(provenance.get("parser_warnings", [])),
            errors=list(provenance.get("parser_errors", [])),
            rows=[self._row_dto_from_repository(row) for row in rows],
            proposed_changes=[self._change_to_dto(change) for change in changes],
        )

    def confirm_import(self, *, import_id: str, confirmation: str) -> PortfolioImportConfirmResultDTO:
        if confirmation != _CONFIRM_TOKEN:
            raise MyPortfolioImportError("confirmation must be the exact token CONFIRM")
        record = self._repo.get_portfolio_import(import_id)
        if record is None:
            raise MyPortfolioImportNotFoundError(f"portfolio import not found: {import_id}")
        provenance = dict(record["provenance"])
        expected_digest = str(provenance.get("base_holdings_digest", ""))
        if not expected_digest:
            raise MyPortfolioImportError("import preview is missing base holdings digest")
        if (
            ImportStatus(str(record["status"])) is ImportStatus.PREVIEWED
            and (
                int(record["rejected_rows"])
                or int(record["unresolved_rows"])
                or int(record["ambiguous_rows"])
            )
        ):
            raise MyPortfolioImportError("import preview has invalid, unresolved, ambiguous, or duplicate rows")

        try:
            already_confirmed, changes = self._repo.confirm_portfolio_import(
                import_id=import_id,
                expected_base_digest=expected_digest,
                confirmed_at=datetime.now(tz=timezone.utc),
            )
        except RepositoryError as exc:
            if "STALE_PREVIEW" in str(exc):
                raise StalePortfolioPreviewError(
                    "STALE_PREVIEW: canonical holdings changed after this preview was created"
                ) from exc
            if "IMPORT_NOT_FOUND" in str(exc):
                raise MyPortfolioImportNotFoundError(f"portfolio import not found: {import_id}") from exc
            raise MyPortfolioImportError(str(exc)) from exc

        refreshed = self._repo.get_portfolio_import(import_id)
        status = ImportStatus(str(refreshed["status"])) if refreshed else ImportStatus.CONFIRMED
        return PortfolioImportConfirmResultDTO(
            import_id=import_id,
            status=status,
            already_confirmed=already_confirmed,
            holdings=self.list_holdings(),
            reconciliation=[self._change_to_dto(change) for change in changes],
        )

    def list_holdings(self) -> list[MyPortfolioHoldingDTO]:
        return [self._holding_to_dto(holding) for holding in self._repo.list_portfolio_holdings()]

    def import_history(self, *, limit: int = 50) -> PortfolioImportHistoryDTO:
        return PortfolioImportHistoryDTO(
            imports=[self._summary_to_dto(row) for row in self._repo.list_portfolio_imports(limit=limit)]
        )

    def reconciliation_history(self, import_id: str) -> list[PortfolioReconciliationChangeDTO]:
        if self._repo.get_portfolio_import(import_id) is None:
            raise MyPortfolioImportNotFoundError(f"portfolio import not found: {import_id}")
        return [
            PortfolioReconciliationChangeDTO(
                instrument_id=str(row["instrument_id"]),
                action=ReconciliationAction(str(row["action"])),
                before=row["before"],
                after=row["after"],
            )
            for row in self._repo.list_portfolio_reconciliations(import_id)
        ]

    def _counts(
        self,
        parser_errors: tuple[str, ...],
        rows: tuple[ResolvedHoldingPreviewRow, ...],
    ) -> dict[str, int]:
        if parser_errors:
            return {
                "total_rows": 0,
                "accepted_rows": 0,
                "rejected_rows": 0,
                "unresolved_rows": 0,
                "ambiguous_rows": 0,
            }
        return {
            "total_rows": len(rows),
            "accepted_rows": sum(1 for row in rows if row.is_confirmable),
            "rejected_rows": sum(1 for row in rows if row.errors),
            "unresolved_rows": sum(1 for row in rows if row.mapping_state is SymbolMappingState.UNRESOLVED),
            "ambiguous_rows": sum(1 for row in rows if row.mapping_state is SymbolMappingState.AMBIGUOUS),
        }

    def _uploaded_holdings_from_preview(
        self,
        import_id: str,
        now: datetime,
        rows: tuple[ResolvedHoldingPreviewRow, ...],
    ) -> dict[str, CanonicalPortfolioHolding]:
        holdings: dict[str, CanonicalPortfolioHolding] = {}
        for row in rows:
            if not row.is_confirmable or row.resolved_instrument_id is None:
                continue
            holdings[row.resolved_instrument_id] = CanonicalPortfolioHolding(
                instrument_id=row.resolved_instrument_id,
                quantity=int(row.parsed.quantity),
                avg_price=Decimal(str(row.parsed.avg_price)),
                imported_at=now,
                updated_at=now,
                source_import_id=import_id,
                source_row_id=row.parsed.source_row_id,
                provenance={"raw_symbol": row.parsed.raw_symbol},
            )
        return holdings

    def _reconciliation_for_import(
        self,
        record: dict[str, object],
        rows: list[dict[str, object]],
    ) -> tuple[ReconciliationChange, ...]:
        if ImportStatus(str(record["status"])) is ImportStatus.CONFIRMED:
            return tuple(
                ReconciliationChange(
                    instrument_id=str(item["instrument_id"]),
                    action=ReconciliationAction(str(item["action"])),
                    before=None,
                    after=None,
                )
                for item in self._repo.list_portfolio_reconciliations(str(record["import_id"]))
            )
        current = {holding.instrument_id: holding for holding in self._repo.list_portfolio_holdings()}
        uploaded: dict[str, CanonicalPortfolioHolding] = {}
        now = datetime.now(tz=timezone.utc)
        for row in rows:
            if row["validation_errors"] or row["mapping_state"] != SymbolMappingState.RESOLVED.value:
                continue
            instrument_id = str(row["resolved_instrument_id"])
            uploaded[instrument_id] = CanonicalPortfolioHolding(
                instrument_id=instrument_id,
                quantity=int(row["quantity"]),
                avg_price=Decimal(str(row["avg_price"])),
                imported_at=now,
                updated_at=now,
                source_import_id=str(record["import_id"]),
                source_row_id=str(row["source_row_id"]),
            )
        return reconcile_current_holdings(current, uploaded)

    def _row_to_repository_dict(self, row: ResolvedHoldingPreviewRow) -> dict[str, object]:
        return {
            "source_row_id": row.parsed.source_row_id,
            "source_row_number": row.parsed.source_row_number,
            "original_values": dict(row.parsed.original_values),
            "normalized_symbol": row.parsed.normalized_symbol,
            "raw_symbol": row.parsed.raw_symbol,
            "quantity": row.parsed.quantity,
            "avg_price": row.parsed.avg_price,
            "mapping_state": row.mapping_state,
            "resolved_instrument_id": row.resolved_instrument_id,
            "validation_errors": list(dict.fromkeys(row.parsed.errors + row.errors)),
            "warnings": list(dict.fromkeys(row.parsed.warnings + row.warnings)),
            "metadata": {"candidates": [asdict(candidate) for candidate in row.candidates]},
        }

    def _row_dto_from_repository(self, row: dict[str, object]) -> ImportedHoldingRowDTO:
        metadata = dict(row["metadata"])
        return ImportedHoldingRowDTO(
            source_row_id=str(row["source_row_id"]),
            raw_symbol=str(row["raw_symbol"]),
            normalized_symbol=str(row["normalized_symbol"]),
            quantity=row["quantity"],
            avg_price=row["avg_price"],
            mapping_state=SymbolMappingState(str(row["mapping_state"])),
            resolved_instrument_id=row["resolved_instrument_id"],
            candidates=list(metadata.get("candidates", [])),
            validation_errors=list(row["validation_errors"]),
            warnings=list(row["warnings"]),
        )

    def _change_to_dto(self, change: ReconciliationChange) -> PortfolioReconciliationChangeDTO:
        return PortfolioReconciliationChangeDTO(
            instrument_id=change.instrument_id,
            action=change.action,
            before=self._holding_json(change.before),
            after=self._holding_json(change.after),
        )

    def _holding_to_dto(self, holding: CanonicalPortfolioHolding) -> MyPortfolioHoldingDTO:
        return MyPortfolioHoldingDTO(
            instrument_id=holding.instrument_id,
            symbol=holding.instrument_id.split(":", 1)[1],
            quantity=holding.quantity,
            avg_price=holding.avg_price,
            investment=holding.avg_price * Decimal(holding.quantity),
            imported_at=holding.imported_at,
            updated_at=holding.updated_at,
            source_import_id=holding.source_import_id,
            source_row_id=holding.source_row_id,
            provenance=dict(holding.provenance),
        )

    def _summary_to_dto(self, row: dict[str, object]) -> PortfolioImportSummaryDTO:
        return PortfolioImportSummaryDTO(
            import_id=str(row["import_id"]),
            filename=str(row["filename"]),
            source=str(row["source"]),
            uploaded_at=row["uploaded_at"],
            holdings_as_of=row["holdings_as_of"],
            parser_version=str(row["parser_version"]),
            status=ImportStatus(str(row["status"])),
            total_rows=int(row["total_rows"]),
            accepted_rows=int(row["accepted_rows"]),
            rejected_rows=int(row["rejected_rows"]),
            unresolved_rows=int(row["unresolved_rows"]),
            ambiguous_rows=int(row["ambiguous_rows"]),
            confirmed_at=row["confirmed_at"],
            provenance=dict(row["provenance"]),
        )

    def _holding_json(self, holding: CanonicalPortfolioHolding | None) -> dict[str, object] | None:
        if holding is None:
            return None
        return {
            "instrument_id": holding.instrument_id,
            "quantity": holding.quantity,
            "avg_price": str(holding.avg_price),
            "source_import_id": holding.source_import_id,
            "source_row_id": holding.source_row_id,
        }
