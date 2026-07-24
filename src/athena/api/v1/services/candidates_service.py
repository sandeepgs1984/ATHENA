"""Owner candidate list service (Market Intelligence validation pool)."""

from __future__ import annotations

from athena.api.exceptions import ResourceNotFoundError
from athena.api.v1.dtos.market import (
    DeleteCandidateResultDTO,
    OwnerCandidateDTO,
    OwnerCandidateListDTO,
    UpsertCandidateRequest,
)
from athena.ops.owner_candidates import CandidateStore, normalize_candidate_symbol


class CandidateNotFoundError(ResourceNotFoundError):
    """Owner candidate symbol not found."""


class CandidatesService:
    def __init__(self, store: CandidateStore) -> None:
        self._store = store

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
