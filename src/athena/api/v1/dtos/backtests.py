"""Backtest resource DTOs (P9.5)."""

from __future__ import annotations

from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field


class StrategyPerformanceDTO(BaseModel):
    """DTO representing strategy performance aggregate results in a backtest."""

    model_config = ConfigDict(frozen=True)

    strategy: str
    total_matches: int
    steps_with_matches: int
    distinct_instruments: int
    instruments: list[str]


class BacktestSummaryDTO(BaseModel):
    """DTO representing the aggregate summary tallies of a backtest session."""

    model_config = ConfigDict(frozen=True)

    total_steps: int
    completed_steps: int
    failed_steps: int
    performance: list[StrategyPerformanceDTO]


class BacktestStepDTO(BaseModel):
    """DTO representing the outcome of one chronological backtest replay date."""

    model_config = ConfigDict(frozen=True)

    replay_date: date
    as_of: datetime
    status: str
    scan_id: str | None = None
    watchlist_snapshot_id: str | None = None
    strategy_execution_id: str | None = None
    note: str


class BacktestRunSummaryDTO(BaseModel):
    """Lightweight DTO summary representing a historical backtest run."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    first_replay_date: date | None = None
    last_replay_date: date | None = None
    meta: dict[str, str] = Field(default_factory=dict)
    total_steps: int
    completed_steps: int
    failed_steps: int


class BacktestRunDTO(BaseModel):
    """Detailed DTO representing a historical backtest run with step chronology."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    first_replay_date: date | None = None
    last_replay_date: date | None = None
    meta: dict[str, str] = Field(default_factory=dict)
    summary: BacktestSummaryDTO
    steps: list[BacktestStepDTO]
