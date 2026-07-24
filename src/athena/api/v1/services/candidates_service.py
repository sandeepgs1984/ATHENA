"""Owner candidate list service (Market Intelligence validation pool)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from athena.api.exceptions import ResourceNotFoundError
from athena.api.v1.dtos.market import (
    DeleteCandidateResultDTO,
    OwnerCandidateDTO,
    OwnerCandidateListDTO,
    UpsertCandidateRequest,
    ValidateSymbolsRequest,
    ValidateSymbolsResultDTO,
)
from athena.calendar.engine import CalendarEngine
from athena.calendar.resolve_as_of import resolve_validate_as_of
from athena.config.loader import load_config
from athena.data.store.repository import SqliteRepository
from athena.errors import AthenaError
from athena.ops.owner_candidates import CandidateStore, normalize_candidate_symbol
from athena.ops.symbol_validate import validate_symbols


class CandidateNotFoundError(ResourceNotFoundError):
    """Owner candidate symbol not found."""


class CandidatesService:
    def __init__(
        self,
        store: CandidateStore,
        *,
        repo: SqliteRepository | None = None,
        config_dir: Path | None = None,
        repo_root: Path | None = None,
    ) -> None:
        self._store = store
        self._repo = repo
        self._config_dir = Path(config_dir) if config_dir else Path("config")
        self._repo_root = Path(repo_root) if repo_root else Path.cwd()

    def list_candidates(self, *, active_only: bool = True) -> OwnerCandidateListDTO:
        rows = self._store.list_candidates(active_only=active_only)
        dtos = tuple(
            OwnerCandidateDTO(
                symbol=c.symbol,
                added_ts=c.added_ts,
                notes=c.notes,
                active=c.active,
            )
            for c in rows
        )
        return OwnerCandidateListDTO(candidates=dtos, count=len(dtos))

    def upsert_candidate(self, body: UpsertCandidateRequest) -> OwnerCandidateDTO:
        row = self._store.upsert_candidate(
            symbol=body.symbol,
            notes=body.notes,
            active=body.active,
        )
        return OwnerCandidateDTO(
            symbol=row.symbol,
            added_ts=row.added_ts,
            notes=row.notes,
            active=row.active,
        )

    def delete_candidate(self, symbol: str) -> DeleteCandidateResultDTO:
        bare = normalize_candidate_symbol(symbol)
        deleted = self._store.delete_candidate(bare)
        if not deleted:
            raise CandidateNotFoundError(f"Candidate '{bare}' not found")
        return DeleteCandidateResultDTO(symbol=bare, deleted=True)

    def validate_candidates(self, body: ValidateSymbolsRequest) -> ValidateSymbolsResultDTO:
        if self._repo is None:
            raise AthenaError(
                "Symbol validate requires the live SQLite ledger "
                "(restart the API so wire_sqlite_providers attaches the DB)"
            )
        cfg = load_config(self._config_dir)
        tz = ZoneInfo(cfg.market.timezone)
        calendar = CalendarEngine.from_config_dir(self._config_dir, cfg.market)
        as_of, as_of_mode = resolve_validate_as_of(datetime.now(tz), calendar, tz)
        result = validate_symbols(
            self._repo,
            self._config_dir,
            symbols=list(body.symbols),
            as_of=as_of,
            repo_root=self._repo_root,
        )
        return ValidateSymbolsResultDTO(
            run_id=result.run_id,
            status=result.status,
            symbols=result.symbols,
            eligible=result.eligible,
            excluded=result.excluded,
            decisions=result.decisions,
            qualified=result.qualified,
            detail=result.detail,
            as_of=as_of,
            as_of_mode=as_of_mode,
        )
