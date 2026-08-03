"""Owner validation candidate list DTOs (Market Intelligence)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class EligibilityRuleDTO(BaseModel):
    """Persisted outcome for one universe-eligibility rule."""

    model_config = ConfigDict(frozen=True)

    rule: str
    passed: bool
    explanation: str


class OwnerCandidateDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    added_ts: datetime
    notes: str = ""
    active: bool = True
    # MI-4 Universe table enrichments — all optional, never fabricated.
    sector: str | None = None
    status: Literal["ELIGIBLE", "EXCLUDED", "PENDING", "UNRESOLVED"] | None = None
    eligibility_summary: str | None = None
    eligibility_evidence: tuple[EligibilityRuleDTO, ...] = ()
    last_validated_ts: datetime | None = None


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
    as_of: datetime | None = None
    as_of_mode: Literal["live", "session_close"] | None = None


class FullValidationProgressDTO(BaseModel):
    """Transient owner-triggered full-universe job progress (ADR-007 / MI-5)."""

    model_config = ConfigDict(frozen=True)

    state: Literal["idle", "running", "completed", "failed"]
    stage: Literal[
        "idle",
        "acquiring_lock",
        "seeding",
        "ingesting",
        "validating",
        "completed",
        "failed",
    ]
    symbols_total: int = 0
    symbols_completed: int = 0
    started_at: datetime | None = None
    finished_at: datetime | None = None
    run_id: str | None = None
    detail: str | None = None


class CandleDTO(BaseModel):
    """One provider-independent OHLCV bar for read-only charting."""

    model_config = ConfigDict(frozen=True)

    ts_open: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    source: str
    adjusted: bool
    atr: Decimal | None = None
    moving_average: Decimal | None = None


class CandleSeriesDTO(BaseModel):
    """Chronological candle series plus explicit data-freshness state."""

    model_config = ConfigDict(frozen=True)

    instrument_id: str
    timeframe: str
    candles: tuple[CandleDTO, ...]
    count: int
    latest_ts: datetime | None
    freshness_status: Literal["FRESH", "STALE", "NO_DATA"]
    age_minutes: int | None
    freshness_threshold_minutes: int


class MarketIndexTickerDTO(BaseModel):
    """One index's level + day-over-day change, from already-persisted Kite
    data only (the latest market snapshot's LTP + the most recent prior
    daily candle close). Both fields are None — never a fabricated 0 or
    placeholder — when the underlying data isn't available yet (ADR-005)."""

    model_config = ConfigDict(frozen=True)

    label: str
    level: Decimal | None = None
    change_pct: Decimal | None = None


class MarketTickerDTO(BaseModel):
    """Header market ticker (DT-2, owner UX workstation refactor). Deliberately
    excludes market breadth (ADV/DEC) and an overall market-health score from
    this compact strip — those live on ``GET /market/summary`` (MH-3 / F-5)."""

    model_config = ConfigDict(frozen=True)

    nifty: MarketIndexTickerDTO
    bank_nifty: MarketIndexTickerDTO
    india_vix: MarketIndexTickerDTO
    as_of: datetime | None = None


class IndexConstituentContextDTO(BaseModel):
    """Versioned membership plus persisted current-board coverage for one index."""

    model_config = ConfigDict(frozen=True)

    effective_date: date
    membership_age_days: int
    source_url: str
    source_sha256: str
    overlap_policy: Literal["COUNT_ONCE_PER_INDEX_INDEPENDENT_ACROSS_INDICES"]
    total_members: int
    resolved_members: int
    unresolved_symbols: tuple[str, ...]
    decision_covered_members: int
    missing_decision_symbols: tuple[str, ...]
    breadth_status: Literal[
        "AVAILABLE",
        "INCOMPLETE_INSTRUMENTS",
        "INCOMPLETE_DECISIONS",
    ]
    trade_count: int | None = None
    watch_count: int | None = None
    no_trade_count: int | None = None
    trade_breadth_pct: Decimal | None = None
    decisions_as_of: datetime | None = None


class IndexIntelligenceItemDTO(BaseModel):
    """One configured broad-market or sector-index observation."""

    model_config = ConfigDict(frozen=True)

    key: str
    label: str
    instrument_id: str
    family: Literal["broad_market", "sectoral"]
    level: Decimal | None = None
    change_pct: Decimal | None = None
    data_status: Literal["AVAILABLE", "NO_DATA"]
    constituents: IndexConstituentContextDTO | None = None


class IndexIntelligenceDTO(BaseModel):
    """Deterministically ordered index observations from one persisted snapshot."""

    model_config = ConfigDict(frozen=True)

    indices: tuple[IndexIntelligenceItemDTO, ...]
    count: int
    available_count: int
    as_of: datetime | None = None
    source: Literal["persisted_market_snapshot"]


class SymbolIndexBackdropDTO(BaseModel):
    """Which official indices contain one symbol, informational only (IX-5).

    `memberships` reuses the exact `IndexIntelligenceItemDTO` objects
    `index_intelligence()` already computes — never a second per-symbol
    calculation. Presentation-only context; never consumed by scoring,
    confidence, risk, or decision policy."""

    model_config = ConfigDict(frozen=True)

    instrument_id: str
    memberships: tuple[IndexIntelligenceItemDTO, ...]


class IndexMemberDTO(BaseModel):
    """One official constituent's resolution and current-board bucket.

    Reuses the exact resolution IX-3 already computes in
    ``_index_constituent_contexts`` (IX-4a) — this is not a second, inferred
    membership mapping."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    instrument_id: str | None = None
    resolved: bool
    bucket: Literal["TRADE", "WATCH", "NO_TRADE"] | None = None


class IndexMembersDTO(BaseModel):
    """Full per-symbol membership list for one official index (IX-4a)."""

    model_config = ConfigDict(frozen=True)

    key: str
    label: str
    effective_date: date
    members: tuple[IndexMemberDTO, ...]


class InstrumentQuoteDTO(BaseModel):
    """Single-instrument last price for the Decisions & Trace header.

    Prefer a live Kite ``/quote`` when credentials are present; otherwise the
    newest persisted SQLite quote. Every numeric field is ``None`` when no real
    value exists (ADR-005 — never fabricate 0).
    """

    model_config = ConfigDict(frozen=True)

    instrument_id: str
    last_price: Decimal | None = None
    change_pct: Decimal | None = None
    as_of: datetime | None = None
    source: Literal["kite_live", "persisted"] | None = None


class MarketRegimeSummaryDTO(BaseModel):
    """Regime labels from the latest validation run (F-5 §8)."""

    model_config = ConfigDict(frozen=True)

    trend: str
    volatility: str
    gap: str
    explanation: str | None = None
    evidence: tuple[str, ...] = ()


class MarketHealthSummaryDTO(BaseModel):
    """Numeric F-5 score when complete, plus honest categorical dimensions."""

    model_config = ConfigDict(frozen=True)

    score: int | None = None
    components: dict[str, int] | None = None
    explanation: str | None = None
    unavailable_reason: str | None = None
    dimensions: dict[str, str] = Field(default_factory=dict)


class MarketBreadthSummaryDTO(BaseModel):
    """Universe ADV/DEC/neutral — never exchange-wide NSE breadth."""

    model_config = ConfigDict(frozen=True)

    advances: int
    declines: int
    neutral: int
    advance_pct: Decimal | None = None
    universe_size: int
    scored: int
    coverage: Decimal | None = None
    label: str = "Universe breadth"


class MarketGapDetailDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    points: int | None = None
    pct: Decimal | None = None


class MarketVixSummaryDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    level: Decimal | None = None
    change_pct: Decimal | None = None


class MarketSparklinesDTO(BaseModel):
    """Persisted D1 closes only — empty when history is missing."""

    model_config = ConfigDict(frozen=True)

    nifty_closes: tuple[Decimal, ...] = ()
    vix_closes: tuple[Decimal, ...] = ()


class MarketSummaryDTO(BaseModel):
    """Market Summary hero read model (MH-3 / F-5 §8). Nulls mean Unavailable."""

    model_config = ConfigDict(frozen=True)

    as_of: datetime | None = None
    available: bool = False
    run_id: str | None = None
    regime: MarketRegimeSummaryDTO | None = None
    market_health: MarketHealthSummaryDTO
    breadth: MarketBreadthSummaryDTO | None = None
    gap_detail: MarketGapDetailDTO | None = None
    vix: MarketVixSummaryDTO | None = None
    sparklines: MarketSparklinesDTO = Field(default_factory=MarketSparklinesDTO)


class OpportunitySymbolDTO(BaseModel):
    """One qualified symbol surfaced under a leading sector ("Top
    Opportunities Today"). Every field is read directly from an already-
    persisted Decision/ScoringResult/ConfidenceAssessment — presentation
    aggregation only, never a new score or recommendation."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    instrument_id: str
    decision_id: str
    decision_type: Literal["TRADE", "WATCH"]
    athena_score: Decimal | None = None
    relative_strength_pct: Decimal | None = None
    confidence_level: Literal["HIGH", "MEDIUM", "LOW"] | None = None
    confidence_stars: int | None = None
    plan_freshness_status: str | None = None
    plan_freshness_summary: str | None = None
    change_badge: Literal["NEW", "IMPROVED", "DROPPED"] | None = None


class OpportunitySectorDTO(BaseModel):
    """One leading sector's rank/performance plus its top qualified symbols."""

    model_config = ConfigDict(frozen=True)

    sector: str
    sector_rank: int
    sector_change_pct: Decimal | None = None
    symbols: tuple[OpportunitySymbolDTO, ...] = ()


class OpportunityRemovedDTO(BaseModel):
    """A symbol surfaced yesterday but no longer surfaced today — sector
    dropped out of the leaders, decision changed, or edged out by a
    stronger symbol in the same sector. Shown separately since it has no
    "today row" of its own to attach a badge to."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    instrument_id: str
    sector: str
    last_seen_score: Decimal | None = None


class OpportunitiesSummaryDTO(BaseModel):
    """Market-snapshot header shown above the sector cards."""

    model_config = ConfigDict(frozen=True)

    strongest_sector: str | None = None
    strongest_sector_change_pct: Decimal | None = None
    strongest_symbol: str | None = None
    highest_athena_score: Decimal | None = None
    average_athena_score: Decimal | None = None
    qualified_sector_count: int = 0
    qualified_symbol_count: int = 0


class TopOpportunitiesDTO(BaseModel):
    """Top Opportunities Today (sector-first): the day's best-performing
    sectors, each contributing its highest-conviction qualified symbols.
    Presentation-only — computed from already-persisted decisions/scores/
    confidence/sector-index data; never influences scoring or decisions."""

    model_config = ConfigDict(frozen=True)

    as_of: datetime
    compared_as_of: datetime | None = None
    summary: OpportunitiesSummaryDTO
    sectors: tuple[OpportunitySectorDTO, ...] = ()
    removed: tuple[OpportunityRemovedDTO, ...] = ()
