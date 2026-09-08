"""My Portfolio import preview and reconciliation service (PS-P2)."""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import threading
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
from io import BytesIO, StringIO
from pathlib import Path
from uuid import uuid4
from xml.sax.saxutils import escape as xml_escape
from zoneinfo import ZoneInfo

from athena.api.exceptions import (
    MyPortfolioHoldingError,
    MyPortfolioHoldingNotFoundError,
    MyPortfolioImportError,
    MyPortfolioImportNotFoundError,
    MyPortfolioSyncNotFoundError,
    PortfolioResetConfirmationError,
    PortfolioSyncActiveConflictError,
    StalePortfolioPreviewError,
)
from athena.api.v1.dtos.portfolio import (
    DeleteMyPortfolioHoldingResultDTO,
    ImportedHoldingRowDTO,
    MyPortfolioHoldingDTO,
    PortfolioAnalysisProvenanceDTO,
    PortfolioDailyReviewDTO,
    PortfolioFreshnessDTO,
    PortfolioImportConfirmResultDTO,
    PortfolioImportHistoryDTO,
    PortfolioImportPreviewDTO,
    PortfolioImportSummaryDTO,
    PortfolioReconciliationChangeDTO,
    PortfolioSnapshotChangesDTO,
    PortfolioSnapshotDTO,
    PortfolioSnapshotFieldChangeDTO,
    PortfolioSnapshotRowChangeDTO,
    PortfolioSnapshotRowDTO,
    PortfolioSnapshotSummaryDTO,
    PortfolioSnapshotTimelineDTO,
    PortfolioSnapshotTimelineEventDTO,
    PortfolioStructuralReviewDTO,
    PortfolioSyncRunDTO,
    ResetMyPortfolioResultDTO,
    SkippedImportRowDTO,
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
    PortfolioSnapshotCurrentness,
    PortfolioSnapshotSummary,
    ReconciliationAction,
    ReconciliationChange,
    SymbolMappingState,
    SyncRunStatus,
    reconcile_current_holdings,
)
from athena.portfolio.snapshot_diff import (
    SnapshotCompareRow,
    diff_snapshot_rows,
)
from athena.portfolio.snapshot_timeline import (
    TimelineSnapshotPoint,
    build_symbol_timeline,
)
from athena.portfolio.sync import PortfolioSyncOrchestrator, utc_now

logger = logging.getLogger(__name__)

_CONFIRM_TOKEN = "CONFIRM"
_RESET_TOKEN = "RESET"
_SYNC_GUARD = threading.Lock()
_SYNC_THREAD: threading.Thread | None = None
_SYNC_THREAD_RUN_ID: str | None = None
_XLSX_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/xl/workbook.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
    '<Override PartName="/xl/worksheets/sheet1.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
    "</Types>"
)
_XLSX_ROOT_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
    'Target="xl/workbook.xml"/>'
    "</Relationships>"
)
_XLSX_WORKBOOK_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
    'Target="worksheets/sheet1.xml"/>'
    "</Relationships>"
)

_SNAPSHOT_EXPORT_COLUMNS = [
    ("no", "No."),
    ("symbol", "Symbol"),
    ("quantity", "Qty"),
    ("avg_price", "Avg Price"),
    ("last_price", "Last Price"),
    ("price_as_of", "Price As Of"),
    ("investment", "Investment"),
    ("current_value", "Current Value"),
    ("pnl", "P&L"),
    ("pnl_pct", "P&L %"),
    ("status", "Status"),
    ("conviction", "Conviction"),
    ("trend_setup", "Trend / Setup"),
    ("daily_review_status", "Daily Review Status"),
    ("supertrend_direction", "SuperTrend Direction"),
    ("supertrend_value", "SuperTrend Value"),
    ("rsi14", "RSI14"),
    ("volume", "Volume"),
    ("volume_ma20", "Volume MA20"),
    ("next_action", "Next Action"),
    ("plan_trigger", "Plan Trigger"),
    ("plan_stop", "Plan Stop"),
    ("plan_t1", "Plan T1"),
    ("structural_support_1", "Structural Support 1"),
    ("structural_major_support", "Structural Major Support"),
    ("structural_review_trigger", "Structural Review Trigger"),
    ("structural_target_1", "Structural Target 1"),
    ("structural_target_2", "Structural Target 2"),
    ("structural_target_3", "Structural Target 3"),
    ("exit_risk", "Exit Risk"),
    ("daily_guidance", "Daily Guidance"),
    ("structural_guidance", "Structural Guidance"),
    ("last_review", "Last Review"),
    ("snapshot_id", "Snapshot ID"),
    ("snapshot_currentness", "Snapshot Currentness"),
]
_HOLDINGS_EXPORT_COLUMNS = [
    ("no", "No."),
    ("instrument_id", "Instrument ID"),
    ("symbol", "Symbol"),
    ("quantity", "Qty"),
    ("avg_price", "Avg Price"),
    ("investment", "Investment"),
    ("imported_at", "Imported At"),
    ("updated_at", "Updated At"),
    ("source_import_id", "Source Import ID"),
    ("source_row_id", "Source Row ID"),
]
_IMPORTS_EXPORT_COLUMNS = [
    ("no", "No."),
    ("import_id", "Import ID"),
    ("filename", "Filename"),
    ("source", "Source"),
    ("uploaded_at", "Uploaded At"),
    ("confirmed_at", "Confirmed At"),
    ("status", "Status"),
    ("total_rows", "Total Rows"),
    ("accepted_rows", "Accepted Rows"),
    ("rejected_rows", "Rejected Rows"),
    ("unresolved_rows", "Unresolved Rows"),
    ("ambiguous_rows", "Ambiguous Rows"),
    ("parser_version", "Parser Version"),
]
_EXPORT_COLUMNS_BY_SCOPE = {
    "snapshot": _SNAPSHOT_EXPORT_COLUMNS,
    "holdings": _HOLDINGS_EXPORT_COLUMNS,
    "imports": _IMPORTS_EXPORT_COLUMNS,
}


@dataclass(frozen=True, slots=True)
class MyPortfolioExportFile:
    """Downloadable My Portfolio export artifact."""

    filename: str
    media_type: str
    content: bytes


class MyPortfolioService:
    """Coordinates My Portfolio import preview, confirmation, and audit reads."""

    SNAPSHOT_TIMELINE_LIMIT = 8

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
        with _SYNC_GUARD:
            self._recover_interrupted_sync_if_needed()
            active = self._repo.get_active_portfolio_sync_run()
            if active is not None:
                raise PortfolioSyncActiveConflictError(
                    "Portfolio Sync is currently running. Wait for it to finish before "
                    "confirming holdings changes."
                )
            record = self._repo.get_portfolio_import(import_id)
            if record is None:
                raise MyPortfolioImportNotFoundError(f"portfolio import not found: {import_id}")
            provenance = dict(record["provenance"])
            expected_digest = str(provenance.get("base_holdings_digest", ""))
            if not expected_digest:
                raise MyPortfolioImportError("import preview is missing base holdings digest")

            # Best-effort, never blocking: any symbol still unresolved purely
            # because it isn't in ATHENA's tracked universe yet is
            # auto-onboarded (the same real ingest "Add & validate" already
            # does) before confirming. A row that's still unresolvable after
            # that, or is structurally invalid data, is simply excluded from
            # the confirmed snapshot and reported back — never a reason to
            # block every other valid row in the same file.
            if ImportStatus(str(record["status"])) is ImportStatus.PREVIEWED:
                self._auto_resolve_unresolved_symbols(import_id)

            try:
                already_confirmed, changes, skipped = self._repo.confirm_portfolio_import(
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
                if "IMPORT_HAS_NO_CONFIRMABLE_HOLDINGS" in str(exc):
                    raise MyPortfolioImportError(
                        "No row in this import could be confirmed — every row is either structurally "
                        "invalid or its symbol could not be resolved, even after attempting to add it "
                        "to ATHENA's tracked instruments. Check the import's rows for details."
                    ) from exc
                raise MyPortfolioImportError(str(exc)) from exc

        refreshed = self._repo.get_portfolio_import(import_id)
        status = ImportStatus(str(refreshed["status"])) if refreshed else ImportStatus.CONFIRMED
        return PortfolioImportConfirmResultDTO(
            import_id=import_id,
            status=status,
            already_confirmed=already_confirmed,
            holdings=self.list_holdings(),
            reconciliation=[self._change_to_dto(change) for change in changes],
            skipped_rows=[
                SkippedImportRowDTO(source_row_id=row.source_row_id, raw_symbol=row.raw_symbol, reason=row.reason)
                for row in skipped
            ],
        )

    def _auto_resolve_unresolved_symbols(self, import_id: str) -> None:
        """Best-effort: onboard any symbol that isn't operationally ready yet
        — either genuinely unresolved, or "resolved" only against ATHENA's
        broader canonical `symbol_master` catalog (ADR-011) with no
        corresponding `instruments` row and therefore no ingested D1 candle
        history. The latter would otherwise confirm successfully and then
        fail Portfolio Sync forever afterwards (owner-reported: GOLDBEES/
        SILVERCASE confirmed fine, then failed every sync with "invalid
        canonical instrument, no persisted d1 candle"). Never attempted for
        a row that was already ambiguous or carried a structural data
        error — resolving the symbol wouldn't fix either of those."""

        if self._config_dir is None:
            return
        symbols: set[str] = set()
        for row in self._repo.list_portfolio_import_rows(import_id):
            mapping_state = str(row["mapping_state"])
            errors = tuple(row["validation_errors"])
            resolved_instrument_id = row["resolved_instrument_id"]
            genuinely_unresolved = (
                mapping_state == SymbolMappingState.UNRESOLVED.value and errors == ("UNRESOLVED_SYMBOL",)
            )
            resolved_but_not_ingested = (
                mapping_state == SymbolMappingState.RESOLVED.value
                and not errors
                and resolved_instrument_id
                and self._repo.get_instrument(str(resolved_instrument_id)) is None
            )
            if genuinely_unresolved or resolved_but_not_ingested:
                symbols.add(str(row["normalized_symbol"]))
        for symbol in sorted(symbols):
            try:
                self._auto_resolve_one_symbol(symbol)
            except Exception:
                # Genuinely bad/delisted/unknown-to-the-provider symbol, no
                # broker session, provider outage, etc. — leave it
                # unresolved; it will be reported as a skipped row rather
                # than blocking the rest of the import.
                logger.warning("My Portfolio auto-resolve failed for %s", symbol, exc_info=True)

    def _auto_resolve_one_symbol(self, symbol: str) -> None:
        from athena.ops.symbol_validate import validate_symbols

        assert self._config_dir is not None  # narrowed by the caller
        bare = self._ensure_candidates_registered([symbol])[0]
        as_of, _tz = self._expected_analysis_session()
        if as_of is None:
            as_of = datetime.now(tz=timezone.utc)
        validate_symbols(self._repo, self._config_dir, symbols=[bare], as_of=as_of, repo_root=self._repo_root)

    def _ensure_candidates_registered(self, symbols: list[str]) -> list[str]:
        """Register any of these symbols as an owner-candidate if it isn't
        one already — a hard prerequisite `validate_symbols` enforces.
        Returns the bare, normalized form of each input symbol, in order.

        Without this, a symbol that only ever reached ATHENA through a
        broader `symbol_master` catalog match (never through "Add &
        validate" or a prior My Portfolio auto-resolve) can never be
        refreshed by Portfolio Sync's own existing auto-refresh mechanism
        either — `validate_symbols` would just keep raising
        "add symbols to the validation list first" on every single sync
        cycle, forever, for that holding.
        """

        from athena.ops.owner_candidates import SqliteCandidateStore, normalize_candidate_symbol

        bare_symbols = [normalize_candidate_symbol(symbol) for symbol in symbols]
        store = SqliteCandidateStore(self._repo)
        known = {c.symbol for c in store.list_candidates(active_only=False)}
        for bare in bare_symbols:
            if bare not in known:
                store.upsert_candidate(symbol=bare, notes="auto-resolved from My Portfolio", active=True)
                known.add(bare)
        return bare_symbols

    def list_holdings(self) -> list[MyPortfolioHoldingDTO]:
        return [self._holding_to_dto(holding) for holding in self._repo.list_portfolio_holdings()]

    def update_holding(
        self, instrument_id: str, *, quantity: int, avg_price: Decimal
    ) -> MyPortfolioHoldingDTO:
        """Owner-initiated correction to one holding's quantity/avg price."""

        with _SYNC_GUARD:
            self._recover_interrupted_sync_if_needed()
            active = self._repo.get_active_portfolio_sync_run()
            if active is not None:
                raise PortfolioSyncActiveConflictError(
                    "Portfolio Sync is currently running. Wait for it to finish before "
                    "editing holdings."
                )
            if self._repo.get_portfolio_holding(instrument_id) is None:
                raise MyPortfolioHoldingNotFoundError(f"portfolio holding not found: {instrument_id}")
            try:
                updated = self._repo.update_portfolio_holding(
                    instrument_id=instrument_id,
                    quantity=quantity,
                    avg_price=avg_price,
                    updated_at=datetime.now(tz=timezone.utc),
                )
            except RepositoryError as exc:
                if "HOLDING_NOT_FOUND" in str(exc):
                    raise MyPortfolioHoldingNotFoundError(
                        f"portfolio holding not found: {instrument_id}"
                    ) from exc
                raise MyPortfolioHoldingError(str(exc)) from exc
        return self._holding_to_dto(updated)

    def delete_holding(self, instrument_id: str) -> DeleteMyPortfolioHoldingResultDTO:
        """Owner-initiated removal of one holding from current My Portfolio."""

        with _SYNC_GUARD:
            self._recover_interrupted_sync_if_needed()
            active = self._repo.get_active_portfolio_sync_run()
            if active is not None:
                raise PortfolioSyncActiveConflictError(
                    "Portfolio Sync is currently running. Wait for it to finish before "
                    "deleting holdings."
                )
            if self._repo.get_portfolio_holding(instrument_id) is None:
                raise MyPortfolioHoldingNotFoundError(f"portfolio holding not found: {instrument_id}")
            deleted = self._repo.delete_portfolio_holding(instrument_id=instrument_id)
        return DeleteMyPortfolioHoldingResultDTO(instrument_id=instrument_id, deleted=deleted)

    def reset_portfolio(self, *, confirmation: str) -> ResetMyPortfolioResultDTO:
        """Owner-triggered full wipe of My Portfolio state only."""

        if confirmation != _RESET_TOKEN:
            raise PortfolioResetConfirmationError("Type RESET to clear My Portfolio.")
        with _SYNC_GUARD:
            self._recover_interrupted_sync_if_needed()
            active = self._repo.get_active_portfolio_sync_run()
            if active is not None:
                raise PortfolioSyncActiveConflictError(
                    "Portfolio Sync is currently running. Wait for it to finish before "
                    "resetting My Portfolio."
                )
            try:
                deleted_counts = self._repo.reset_my_portfolio()
            except RepositoryError as exc:
                raise MyPortfolioHoldingError(str(exc)) from exc
        return ResetMyPortfolioResultDTO(deleted_counts=deleted_counts)

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
        currentness = self._snapshot_currentness(run)
        return PortfolioSnapshotDTO(
            snapshot_id=str(run["sync_run_id"]),
            generated_at=run["finished_at"] or run["started_at"],
            currentness=currentness["currentness"],
            portfolio_changed_since_sync=bool(currentness["portfolio_changed_since_sync"]),
            currentness_reason=str(currentness["currentness_reason"]),
            snapshot_holdings_digest=currentness["snapshot_holdings_digest"],
            current_holdings_digest=currentness["current_holdings_digest"],
            summary=summary,
            rows=row_dtos,
        )

    def snapshot_changes_since_previous(self) -> PortfolioSnapshotChangesDTO:
        """Compare the latest snapshot with the previous completed snapshot.

        Display-only. Never recalculates Portfolio Intelligence.
        """

        current = self.latest_snapshot()
        previous_run = self._repo.previous_portfolio_snapshot_sync_run(current.snapshot_id)
        if previous_run is None:
            return PortfolioSnapshotChangesDTO(
                current_snapshot_id=current.snapshot_id,
                previous_snapshot_id=None,
                previous_generated_at=None,
                comparison_available=False,
                portfolio_changed_since_sync=current.portfolio_changed_since_sync,
                currentness=current.currentness,
                note="No previous completed snapshot to compare.",
                rows=[],
            )
        previous_rows = [
            self._snapshot_row_to_dto(row)
            for row in self._repo.list_portfolio_analysis_snapshots(
                str(previous_run["sync_run_id"])
            )
        ]
        changes = diff_snapshot_rows(
            tuple(self._snapshot_compare_row(row) for row in previous_rows),
            tuple(self._snapshot_compare_row(row) for row in current.rows),
        )
        note = None
        if current.portfolio_changed_since_sync:
            note = (
                "Compared with the previous analysis snapshot. "
                "Holdings changed after the latest sync."
            )
        return PortfolioSnapshotChangesDTO(
            current_snapshot_id=current.snapshot_id,
            previous_snapshot_id=str(previous_run["sync_run_id"]),
            previous_generated_at=previous_run["finished_at"] or previous_run["started_at"],
            comparison_available=True,
            portfolio_changed_since_sync=current.portfolio_changed_since_sync,
            currentness=current.currentness,
            note=note,
            rows=[
                PortfolioSnapshotRowChangeDTO(
                    instrument_id=change.instrument_id,
                    symbol=change.symbol,
                    presence=change.presence,
                    badges=list(change.badges),
                    fields=[
                        PortfolioSnapshotFieldChangeDTO(
                            field_id=field.field_id,
                            label=field.label,
                            previous=field.previous,
                            current=field.current,
                        )
                        for field in change.fields
                    ],
                )
                for change in changes
            ],
        )

    def snapshot_review_timeline(self, instrument_id: str) -> PortfolioSnapshotTimelineDTO:
        """Build a display-only review timeline for one holding.

        Uses recent SUCCESS/PARTIAL snapshots that already have rows.
        Never recalculates Portfolio Intelligence.
        """

        requested = instrument_id.strip()
        if not requested:
            raise MyPortfolioHoldingError("instrument_id is required")
        current = self.latest_snapshot()
        runs = self._repo.list_portfolio_snapshot_sync_runs(limit=self.SNAPSHOT_TIMELINE_LIMIT)
        chronological = tuple(reversed(runs))
        points: list[TimelineSnapshotPoint] = []
        symbol = requested
        appeared = False
        for run in chronological:
            rows = [
                self._snapshot_row_to_dto(record)
                for record in self._repo.list_portfolio_analysis_snapshots(
                    str(run["sync_run_id"])
                )
            ]
            match = next(
                (
                    row
                    for row in rows
                    if requested
                    in {
                        row.provenance.instrument_id,
                        row.symbol,
                    }
                ),
                None,
            )
            if match is not None:
                appeared = True
                symbol = match.symbol
            points.append(
                TimelineSnapshotPoint(
                    snapshot_id=str(run["sync_run_id"]),
                    generated_at=run["finished_at"] or run["started_at"],
                    sync_status=str(run["status"]),
                    row=self._snapshot_compare_row(match) if match is not None else None,
                )
            )
        events = build_symbol_timeline(points)
        latest_status = str(runs[0]["status"]) if runs else None
        if len(runs) < 2:
            note = "Two completed snapshots are required to build a review timeline."
            comparison_available = False
        elif not appeared:
            note = "This holding is not in the recent snapshots."
            comparison_available = True
        elif not events:
            note = "No tracked fields changed across recent snapshots."
            comparison_available = True
        else:
            note = None
            comparison_available = True
        if latest_status == SyncRunStatus.PARTIAL.value:
            extra = "Latest snapshot is a partial sync."
            note = f"{note} {extra}" if note else extra
        return PortfolioSnapshotTimelineDTO(
            instrument_id=requested,
            symbol=symbol,
            current_snapshot_id=current.snapshot_id,
            snapshot_count=len(runs),
            comparison_available=comparison_available,
            note=note,
            events=[
                PortfolioSnapshotTimelineEventDTO(
                    snapshot_id=event.snapshot_id,
                    previous_snapshot_id=event.previous_snapshot_id,
                    generated_at=event.generated_at,
                    sync_status=SyncRunStatus(event.sync_status),
                    presence=event.presence,
                    badges=list(event.badges),
                    fields=[
                        PortfolioSnapshotFieldChangeDTO(
                            field_id=field.field_id,
                            label=field.label,
                            previous=field.previous,
                            current=field.current,
                        )
                        for field in event.fields
                    ],
                )
                for event in events
            ],
        )

    def _snapshot_compare_row(self, row: PortfolioSnapshotRowDTO) -> SnapshotCompareRow:
        structural = row.structural_review
        support = None
        structural_target = None
        if structural is not None and structural.support_1 is not None:
            support = self._zone_text(structural.support_1)
        if structural is not None and structural.target_1 is not None:
            structural_target = structural.target_1.lower
        return SnapshotCompareRow(
            instrument_id=row.provenance.instrument_id,
            symbol=row.symbol,
            status=row.status,
            daily_review_status=(
                row.daily_review.review_status if row.daily_review is not None else None
            ),
            next_action=row.next_action,
            trend_setup=row.trend_setup,
            pnl_pct=row.pnl_pct,
            current_value=row.current_value,
            last_price=row.last_price,
            plan_t1=row.target_1,
            support_1=support,
            structural_target_1=structural_target,
            daily_guidance=row.daily_review.guidance if row.daily_review is not None else None,
            structural_guidance=(
                structural.guidance if structural is not None else None
            ),
        )

    def export_portfolio(
        self,
        *,
        scope: str,
        format_: str,
        columns: str | None = None,
    ) -> MyPortfolioExportFile:
        """Build a downloadable export from existing My Portfolio state.

        Exports are read-only projections over already-persisted holdings,
        imports, and snapshots. They never recalculate Portfolio Intelligence.
        """

        normalized_scope = scope.lower().strip()
        normalized_format = format_.lower().strip()
        if normalized_scope not in {"snapshot", "holdings", "imports"}:
            raise MyPortfolioHoldingError("export scope must be one of: snapshot, holdings, imports")
        if normalized_format not in {"csv", "xlsx", "json"}:
            raise MyPortfolioHoldingError("export format must be one of: csv, xlsx, json")
        selected_column_ids = self._normalize_export_columns(normalized_scope, columns)

        generated_at = datetime.now(tz=timezone.utc)
        if normalized_scope == "snapshot":
            snapshot = self.latest_snapshot()
            headers, rows = self._snapshot_export_table(snapshot)
            payload: object = snapshot.model_dump(mode="json", by_alias=True)
            timestamp = snapshot.generated_at
        elif normalized_scope == "holdings":
            holdings = self.list_holdings()
            headers, rows = self._holdings_export_table(holdings)
            payload = {
                "generated_at": generated_at.isoformat(),
                "holdings": [h.model_dump(mode="json") for h in holdings],
            }
            timestamp = generated_at
        else:
            imports = self.import_history(limit=500)
            headers, rows = self._imports_export_table(imports)
            payload = imports.model_dump(mode="json")
            timestamp = generated_at

        column_ids = [column_id for column_id, _label in _EXPORT_COLUMNS_BY_SCOPE[normalized_scope]]
        if selected_column_ids is not None:
            headers, rows = self._filter_export_table(
                column_ids=column_ids,
                headers=headers,
                rows=rows,
                selected_column_ids=selected_column_ids,
            )
            if normalized_format == "json":
                payload = {
                    "generated_at": generated_at.isoformat(),
                    "scope": normalized_scope,
                    "columns": [
                        {"id": column_id, "label": header}
                        for column_id, header in zip(selected_column_ids, headers, strict=True)
                    ],
                    "rows": [
                        {
                            column_id: self._export_cell(value)
                            for column_id, value in zip(selected_column_ids, row, strict=True)
                        }
                        for row in rows
                    ],
                }

        stem = self._export_filename_stem(normalized_scope, timestamp)
        if normalized_format == "json":
            content = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
            return MyPortfolioExportFile(f"{stem}.json", "application/json", content)
        if normalized_format == "csv":
            return MyPortfolioExportFile(
                f"{stem}.csv",
                "text/csv; charset=utf-8",
                self._csv_export_bytes(headers, rows),
            )
        return MyPortfolioExportFile(
            f"{stem}.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            self._xlsx_export_bytes(self._export_sheet_name(normalized_scope), headers, rows),
        )

    def _snapshot_currentness(
        self,
        run: dict[str, object],
    ) -> dict[str, object]:
        provenance = dict(run.get("provenance") or {})
        snapshot_digest = provenance.get("holdings_digest")
        current_digest = self._repo.portfolio_holdings_digest()
        if not snapshot_digest:
            return {
                "currentness": PortfolioSnapshotCurrentness.UNKNOWN,
                "portfolio_changed_since_sync": False,
                "currentness_reason": "SNAPSHOT_HOLDINGS_DIGEST_UNAVAILABLE",
                "snapshot_holdings_digest": None,
                "current_holdings_digest": current_digest,
            }
        if str(snapshot_digest) == current_digest:
            return {
                "currentness": PortfolioSnapshotCurrentness.CURRENT,
                "portfolio_changed_since_sync": False,
                "currentness_reason": "SNAPSHOT_MATCHES_CURRENT_HOLDINGS",
                "snapshot_holdings_digest": str(snapshot_digest),
                "current_holdings_digest": current_digest,
            }
        return {
            "currentness": PortfolioSnapshotCurrentness.STALE_HOLDINGS_CHANGED,
            "portfolio_changed_since_sync": True,
            "currentness_reason": "STALE_HOLDINGS_CHANGED",
            "snapshot_holdings_digest": str(snapshot_digest),
            "current_holdings_digest": current_digest,
        }

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
            config_dir=self._config_dir or Path("config"),
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

            # A holding whose instrument only ever came from a `symbol_master`
            # catalog match (never "Add & validate", never a prior My
            # Portfolio auto-resolve) is never yet a registered owner
            # candidate — validate_symbols hard-requires that, so register
            # first rather than let it raise on every refresh attempt.
            bare_symbols = self._ensure_candidates_registered(list(symbols))
            result = validate_symbols(
                self._repo,
                self._config_dir,
                symbols=bare_symbols,
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
        daily_review = payload.pop("daily_review", None)
        structural_review = payload.pop("structural_review", None)
        return PortfolioSnapshotRowDTO(
            **payload,
            daily_review=(
                PortfolioDailyReviewDTO(**dict(daily_review))
                if isinstance(daily_review, dict)
                else None
            ),
            structural_review=(
                PortfolioStructuralReviewDTO(**dict(structural_review))
                if isinstance(structural_review, dict)
                else None
            ),
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

    def _snapshot_export_table(
        self,
        snapshot: PortfolioSnapshotDTO,
    ) -> tuple[list[str], list[list[object]]]:
        headers = [label for _column_id, label in _SNAPSHOT_EXPORT_COLUMNS]
        rows: list[list[object]] = []
        for index, row in enumerate(snapshot.rows, start=1):
            daily = row.daily_review
            structural = row.structural_review
            rows.append(
                [
                    index,
                    row.symbol,
                    row.quantity,
                    row.avg_price,
                    row.last_price,
                    row.price_as_of,
                    row.investment,
                    row.current_value,
                    row.pnl,
                    row.pnl_pct,
                    row.status,
                    row.conviction,
                    row.trend_setup,
                    daily.review_status if daily else None,
                    daily.supertrend_direction if daily else None,
                    daily.supertrend_value if daily else None,
                    daily.rsi14 if daily else None,
                    daily.volume if daily else None,
                    daily.volume_ma20 if daily else None,
                    row.next_action,
                    row.key_trigger,
                    row.major_support_exit,
                    row.target_1,
                    self._zone_text(structural.support_1 if structural else None),
                    self._zone_text(structural.major_support if structural else None),
                    self._zone_text(structural.review_trigger if structural else None),
                    self._zone_text(structural.target_1 if structural else None),
                    self._zone_text(structural.target_2 if structural else None),
                    self._zone_text(structural.target_3 if structural else None),
                    structural.exit_risk if structural else None,
                    daily.guidance if daily else None,
                    structural.guidance if structural else None,
                    row.last_review,
                    snapshot.snapshot_id,
                    snapshot.currentness.value,
                ]
            )
        return headers, rows

    def _holdings_export_table(
        self,
        holdings: list[MyPortfolioHoldingDTO],
    ) -> tuple[list[str], list[list[object]]]:
        headers = [label for _column_id, label in _HOLDINGS_EXPORT_COLUMNS]
        rows = [
            [
                index,
                holding.instrument_id,
                holding.symbol,
                holding.quantity,
                holding.avg_price,
                holding.investment,
                holding.imported_at,
                holding.updated_at,
                holding.source_import_id,
                holding.source_row_id,
            ]
            for index, holding in enumerate(holdings, start=1)
        ]
        return headers, rows

    def _imports_export_table(
        self,
        history: PortfolioImportHistoryDTO,
    ) -> tuple[list[str], list[list[object]]]:
        headers = [label for _column_id, label in _IMPORTS_EXPORT_COLUMNS]
        rows = [
            [
                index,
                item.import_id,
                item.filename,
                item.source,
                item.uploaded_at,
                item.confirmed_at,
                item.status.value,
                item.total_rows,
                item.accepted_rows,
                item.rejected_rows,
                item.unresolved_rows,
                item.ambiguous_rows,
                item.parser_version,
            ]
            for index, item in enumerate(history.imports, start=1)
        ]
        return headers, rows

    def _normalize_export_columns(self, scope: str, columns: str | None) -> list[str] | None:
        if columns is None or not columns.strip():
            return None
        allowed = {column_id for column_id, _label in _EXPORT_COLUMNS_BY_SCOPE[scope]}
        selected: list[str] = []
        invalid: list[str] = []
        for raw_column in columns.split(","):
            column_id = raw_column.strip().lower()
            if not column_id:
                continue
            if column_id not in allowed:
                invalid.append(column_id)
                continue
            if column_id not in selected:
                selected.append(column_id)
        if invalid:
            allowed_text = ", ".join(column_id for column_id, _label in _EXPORT_COLUMNS_BY_SCOPE[scope])
            raise MyPortfolioHoldingError(
                f"unknown export column(s): {', '.join(invalid)}; allowed columns: {allowed_text}"
            )
        if not selected:
            raise MyPortfolioHoldingError("export columns must include at least one known column")
        return selected

    def _filter_export_table(
        self,
        *,
        column_ids: list[str],
        headers: list[str],
        rows: list[list[object]],
        selected_column_ids: list[str],
    ) -> tuple[list[str], list[list[object]]]:
        indexes = [column_ids.index(column_id) for column_id in selected_column_ids]
        return [headers[index] for index in indexes], [[row[index] for index in indexes] for row in rows]

    def _zone_text(self, zone: object | None) -> str:
        if zone is None:
            return ""
        lower = getattr(zone, "lower", None)
        upper = getattr(zone, "upper", None)
        if lower is None or upper is None:
            return ""
        return f"{lower}-{upper}"

    def _export_filename_stem(self, scope: str, timestamp: datetime) -> str:
        return f"athena-my-portfolio-{scope}-{timestamp:%Y%m%d-%H%M%SZ}"

    def _export_sheet_name(self, scope: str) -> str:
        return {
            "snapshot": "Latest Snapshot",
            "holdings": "Confirmed Holdings",
            "imports": "Import History",
        }[scope]

    def _csv_export_bytes(self, headers: list[str], rows: list[list[object]]) -> bytes:
        buffer = StringIO(newline="")
        writer = csv.writer(buffer)
        writer.writerow(headers)
        writer.writerows([[self._export_cell(value) for value in row] for row in rows])
        return buffer.getvalue().encode("utf-8-sig")

    def _xlsx_export_bytes(
        self,
        sheet_name: str,
        headers: list[str],
        rows: list[list[object]],
    ) -> bytes:
        data = [headers, *[[self._export_cell(value) for value in row] for row in rows]]
        sheet_xml = self._xlsx_sheet_xml(data)
        out = BytesIO()
        with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as workbook:
            workbook.writestr("[Content_Types].xml", _XLSX_CONTENT_TYPES)
            workbook.writestr("_rels/.rels", _XLSX_ROOT_RELS)
            workbook.writestr("xl/workbook.xml", self._xlsx_workbook_xml(sheet_name))
            workbook.writestr("xl/_rels/workbook.xml.rels", _XLSX_WORKBOOK_RELS)
            workbook.writestr("xl/worksheets/sheet1.xml", sheet_xml)
        return out.getvalue()

    def _xlsx_workbook_xml(self, sheet_name: str) -> str:
        escaped_name = xml_escape(sheet_name)
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f'<sheets><sheet name="{escaped_name}" sheetId="1" r:id="rId1"/></sheets>'
            "</workbook>"
        )

    def _xlsx_sheet_xml(self, rows: list[list[str]]) -> str:
        row_xml = []
        for row_index, row in enumerate(rows, start=1):
            cells = []
            for col_index, value in enumerate(row, start=1):
                ref = f"{self._xlsx_column_name(col_index)}{row_index}"
                cells.append(
                    f'<c r="{ref}" t="inlineStr"><is><t>{xml_escape(value)}</t></is></c>'
                )
            row_xml.append(f'<row r="{row_index}">{"".join(cells)}</row>')
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            "<sheetViews><sheetView workbookViewId=\"0\"><pane ySplit=\"1\" "
            'topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
            f'<sheetData>{"".join(row_xml)}</sheetData>'
            "</worksheet>"
        )

    def _xlsx_column_name(self, index: int) -> str:
        name = ""
        while index:
            index, rem = divmod(index - 1, 26)
            name = chr(65 + rem) + name
        return name

    def _export_cell(self, value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Decimal):
            return format(value, "f")
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        return str(value)

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
            daily_review=(
                row.daily_review.model_dump(mode="json")
                if row.daily_review is not None
                else None
            ),
            structural_review=(
                row.structural_review.model_dump(mode="json")
                if row.structural_review is not None
                else None
            ),
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
                interpretation_version=row.provenance.interpretation_version,
                interpretation_reason_codes=tuple(row.provenance.interpretation_reason_codes),
                daily_review_version=row.provenance.daily_review_version,
                daily_review_reason_codes=tuple(row.provenance.daily_review_reason_codes),
                daily_review_evidence=row.provenance.daily_review_evidence,
                interpretation_evidence=dict(row.provenance.interpretation_evidence),
            ),
        )
