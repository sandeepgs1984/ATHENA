"""Owner validation candidate list DTOs (Market Intelligence)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OwnerCandidateDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    added_ts: datetime
    notes: str = ""
    active: bool = True


class OwnerCandidateListDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidates: tuple[OwnerCandidateDTO, ...]
    count: int


class UpsertCandidateRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str = Field(..., min_length=1, description="Trading symbol, e.g. INFY or NSE:INFY")
    notes: str = Field(default="", max_length=500)
    active: bool = True


class DeleteCandidateResultDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    deleted: bool


class ValidateSymbolsRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbols: list[str] = Field(..., min_length=1, max_length=20)


class ValidateSymbolsResultDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    status: str
    symbols: tuple[str, ...]
    eligible: int
    excluded: int
    decisions: int
    qualified: int
    detail: str = ""
