"""My Portfolio import preview and reconciliation service (PS-P2)."""

from __future__ import annotations

import hashlib
import threading
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from athena.api.exceptions import (
    MyPortfolioImportError,
    MyPortfolioImportNotFoundError,
    MyPortfolioSyncNotFoundError,
    StalePortfolioPreviewError,
)
from athena.api.v1.dtos.portfolio import (
    ImportedHoldingRowDTO,
    MyPortfolioHoldingDTO,
    PortfolioAnalysisProvenanceDTO,
    PortfolioFreshnessDTO,
    PortfolioImportConfirmResultDTO,
    PortfolioImportHistoryDTO,
    PortfolioImportPreviewDTO,
    PortfolioImportSummaryDTO,
    PortfolioReconciliationChangeDTO,
    PortfolioSnapshotDTO,
    PortfolioSnapshotRowDTO,
    PortfolioSnapshotSummaryDTO,
    PortfolioSyncRunDTO,
)
from athena.calendar.engine import CalendarEngine
from athena.calendar.resolve_as_of import resolve_validate_as_of
from athena.config.loader import load_config
from athena.data.store.repository import SqliteRepository
from athena.errors import RepositoryError
from athena.portfolio.imports import (
    ResolvedHoldingPreviewRow,
    build_symbol_resolver_index,
    parse_holdings_file,
    resolve_preview_rows,
)
from athena.portfolio.my_portfolio_contracts import (
    PORTFOLIO_ANALYSIS_VERSION,
    CanonicalPortfolioHolding,
    ImportStatus,
    PortfolioSnapshotSummary,
    ReconciliationAction,
    ReconciliationChange,
    SymbolMappingState,
    SyncRunStatus,
    reconcile_current_holdings,
)
from athena.portfolio.sync import PortfolioSyncOrchestrator, utc_now

_CONFIRM_TOKEN = "CONFIRM"
_SYNC_GUARD = threading.Lock()
_SYNC_THREAD: threading.Thread | None = None
_SYNC_THREAD_RUN_ID: str | None = None


class MyPortfolioService:
    """Coordinates My Portfolio import preview, confirmation, and audit reads."""

    def __init__(
        self,
        repo: SqliteRepository,
        *,
        config_dir: Path | None = None,
        repo_root: Path | None = None,
    ) -> None:
        self._repo = repo
        self._config_dir = config_dir
        self._repo_root = repo_root

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

    def start_sync(self, *, force_ingestion: bool = False) -> PortfolioSyncRunDTO:
        """Start a single-flight background Portfolio Sync run."""

        global _SYNC_THREAD, _SYNC_THREAD_RUN_ID
        orchestrator = self._portfolio_sync_orchestrator(force_ingestion=force_ingestion)
        with _SYNC_GUARD:
            active = self._repo.get_active_portfolio_sync_run()
            if active is not None:
                if (
                    _SYNC_THREAD is not None
                    and _SYNC_THREAD.is_alive()
                    and active["sync_run_id"] == _SYNC_THREAD_RUN_ID
                ):
                    return self._sync_run_to_dto(active)
                self._repo.mark_interrupted_portfolio_sync_runs(interrupted_at=utc_now())

            run = orchestrator.create_run()
            thread = threading.Thread(
                target=self._run_sync_worker,
                name="athena-my-portfolio-sync",
                daemon=True,
                args=(str(run["sync_run_id"]), force_ingestion),
            )
            _SYNC_THREAD = thread
            _SYNC_THREAD_RUN_ID = str(run["sync_run_id"])
            thread.start()
            return self._sync_run_to_dto(run)

    def run_sync_inline(self, *, force_ingestion: bool = False) -> PortfolioSyncRunDTO:
        """Deterministic test helper: create and run a sync in the current thread."""

        orchestrator = self._portfolio_sync_orchestrator(force_ingestion=force_ingestion)
        self._repo.mark_interrupted_portfolio_sync_runs(interrupted_at=utc_now())
        run = orchestrator.create_run()
        return self._sync_run_to_dto(orchestrator.run(str(run["sync_run_id"])))

    def get_sync(self, sync_run_id: str) -> PortfolioSyncRunDTO:
        self._recover_interrupted_sync_if_needed()
        run = self._repo.get_portfolio_sync_run(sync_run_id)
        if run is None:
            raise MyPortfolioSyncNotFoundError(f"portfolio sync not found: {sync_run_id}")
        return self._sync_run_to_dto(run)

    def sync_history(self, *, limit: int = 50) -> list[PortfolioSyncRunDTO]:
        self._recover_interrupted_sync_if_needed()
        return [
            self._sync_run_to_dto(row)
            for row in self._repo.list_portfolio_sync_runs(limit=limit)
        ]

    def latest_snapshot(self) -> PortfolioSnapshotDTO:
        self._recover_interrupted_sync_if_needed()
        run = self._repo.latest_portfolio_snapshot_sync_run()
        if run is None:
            raise MyPortfolioSyncNotFoundError("no completed My Portfolio snapshot exists")
        rows = self._repo.list_portfolio_analysis_snapshots(str(run["sync_run_id"]))
        if not rows:
            raise MyPortfolioSyncNotFoundError("no completed My Portfolio snapshot exists")
        row_dtos = [self._snapshot_row_to_dto(row) for row in rows]
        summary = self._snapshot_summary_to_dto(run, row_dtos)
        return PortfolioSnapshotDTO(
            snapshot_id=str(run["sync_run_id"]),
            generated_at=run["finished_at"] or run["started_at"],
            summary=summary,
            rows=row_dtos,
        )

    def _run_sync_worker(self, sync_run_id: str, force_ingestion: bool) -> None:
        try:
            self._portfolio_sync_orchestrator(
                force_ingestion=force_ingestion,
            ).run(sync_run_id)
        except Exception as exc:
            self._repo.update_portfolio_sync_run(
                sync_run_id,
                status=SyncRunStatus.FAILED,
                finished_at=utc_now(),
                error={"code": "SYNC_WORKER_FAILED", "message": str(exc)},
                progress={
                    "stage": "failed",
                    "message": "Portfolio Sync failed before completion",
                },
            )
        finally:
            self._repo.close_read_connection()

    def _portfolio_sync_orchestrator(
        self,
        *,
        force_ingestion: bool = False,
    ) -> PortfolioSyncOrchestrator:
        expected_analysis_as_of, market_timezone = self._expected_analysis_session()
        return PortfolioSyncOrchestrator(
            self._repo,
            validation_runner=self._validation_runner(),
            expected_analysis_as_of=expected_analysis_as_of,
            market_timezone=market_timezone,
            force_ingestion=force_ingestion,
        )

    def _expected_analysis_session(self) -> tuple[datetime | None, ZoneInfo | None]:
        if self._config_dir is None:
            return None, None
        cfg = load_config(self._config_dir)
        tz = ZoneInfo(cfg.market.timezone)
        calendar = CalendarEngine.from_config_dir(self._config_dir, cfg.market)
        as_of, _mode = resolve_validate_as_of(datetime.now(tz), calendar, tz)
        return as_of, tz

    def _recover_interrupted_sync_if_needed(self) -> None:
        active = self._repo.get_active_portfolio_sync_run()
        if active is None:
            return
        if (
            _SYNC_THREAD is not None
            and _SYNC_THREAD.is_alive()
            and active["sync_run_id"] == _SYNC_THREAD_RUN_ID
        ):
            return
        self._repo.mark_interrupted_portfolio_sync_runs(interrupted_at=utc_now())

    def _validation_runner(self):
        if self._config_dir is None:
            return None

        def run(symbols, as_of: datetime) -> str | None:
            from athena.ops.symbol_validate import validate_symbols

            result = validate_symbols(
                self._repo,
                self._config_dir,
                symbols=list(symbols),
                as_of=as_of,
                repo_root=self._repo_root,
            )
            return result.run_id

        return run

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

    def _sync_run_to_dto(self, row: dict[str, object]) -> PortfolioSyncRunDTO:
        return PortfolioSyncRunDTO(
            sync_run_id=str(row["sync_run_id"]),
            status=SyncRunStatus(str(row["status"])),
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            total_holdings=int(row["total_holdings"]),
            succeeded_holdings=int(row["succeeded_holdings"]),
            failed_holdings=int(row["failed_holdings"]),
            market_data_through=row["market_data_through"],
            validation_run_id=row["validation_run_id"],
            analysis_version=str(row["analysis_version"]),
            progress=dict(row["progress"]),
            per_symbol=dict(row["per_symbol"]),
            error=dict(row["error"]),
        )

    def _snapshot_row_to_dto(self, row: dict[str, object]) -> PortfolioSnapshotRowDTO:
        payload = dict(row["row"])
        freshness = dict(payload.pop("freshness"))
        provenance = dict(payload.pop("provenance"))
        return PortfolioSnapshotRowDTO(
            **payload,
            freshness=PortfolioFreshnessDTO(**freshness),
            provenance=PortfolioAnalysisProvenanceDTO(**provenance),
        )

    def _snapshot_summary_to_dto(
        self,
        run: dict[str, object],
        rows: list[PortfolioSnapshotRowDTO],
    ) -> PortfolioSnapshotSummaryDTO:
        imports = self._repo.list_portfolio_imports(limit=200)
        latest_confirmed = next(
            (item for item in imports if ImportStatus(str(item["status"])) is ImportStatus.CONFIRMED),
            None,
        )
        summary = PortfolioSnapshotSummary.from_rows(
            tuple(self._dto_row_to_contract_row(row) for row in rows),
            imported_at=latest_confirmed["confirmed_at"] if latest_confirmed else None,
            holdings_as_of=latest_confirmed["holdings_as_of"] if latest_confirmed else None,
            last_synced_at=run["finished_at"],
            market_data_through=run["market_data_through"],
            sync_status=SyncRunStatus(str(run["status"])),
        )
        return PortfolioSnapshotSummaryDTO(
            holding_count=summary.holding_count,
            total_investment=summary.total_investment,
            total_current_value=summary.total_current_value,
            total_pnl=summary.total_pnl,
            total_pnl_pct=summary.total_pnl_pct,
            imported_at=summary.imported_at,
            holdings_as_of=summary.holdings_as_of,
            last_synced_at=summary.last_synced_at,
            market_data_through=summary.market_data_through,
            sync_status=summary.sync_status,
        )

    def _dto_row_to_contract_row(self, row: PortfolioSnapshotRowDTO):
        from athena.portfolio.my_portfolio_contracts import (
            PortfolioAnalysisProvenance,
            PortfolioFreshness,
            PortfolioSnapshotRow,
        )

        return PortfolioSnapshotRow(
            symbol=row.symbol,
            quantity=row.quantity,
            avg_price=row.avg_price,
            last_price=row.last_price,
            price_as_of=row.price_as_of,
            investment=row.investment,
            current_value=row.current_value,
            pnl=row.pnl,
            pnl_pct=row.pnl_pct,
            status=row.status,
            conviction=row.conviction,
            trend_setup=row.trend_setup,
            key_trigger=row.key_trigger,
            support_1=row.support_1,
            major_support_exit=row.major_support_exit,
            target_1=row.target_1,
            target_2=row.target_2,
            target_3=row.target_3,
            next_action=row.next_action,
            last_review=row.last_review,
            freshness=PortfolioFreshness(
                portfolio_imported_at=row.freshness.portfolio_imported_at,
                holdings_as_of=row.freshness.holdings_as_of,
                last_synced_at=row.freshness.last_synced_at,
                market_data_through=row.freshness.market_data_through,
                analysis_version=PORTFOLIO_ANALYSIS_VERSION,
                decision_as_of=row.freshness.decision_as_of,
                price_as_of=row.freshness.price_as_of,
            ),
            provenance=PortfolioAnalysisProvenance(
                instrument_id=row.provenance.instrument_id,
                price_source=row.provenance.price_source,
                candle_ref=row.provenance.candle_ref,
                decision_id=row.provenance.decision_id,
                validation_run_id=row.provenance.validation_run_id,
                analyzed_at=row.provenance.analyzed_at,
                unavailable_fields=tuple(row.provenance.unavailable_fields),
                failed_components=tuple(row.provenance.failed_components),
            ),
        )
