"""Strategy resource DTOs (P9.5)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class StrategyProfileDTO(BaseModel):
    """DTO representing a strategy profile configuration and selection rules."""

    model_config = ConfigDict(frozen=True)

    name: str
    enabled: bool
    description: str
    decisions: list[str]
    direction: str | None = None
    watchlists_any: list[str] = Field(default_factory=list)
    min_score: int | None = None
    min_confidence: int | None = None
    max_risk: int | None = None
