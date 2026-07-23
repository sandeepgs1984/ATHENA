"""Pydantic models for every configuration layer (ATHENA-002 §6).

Validation philosophy: fail fast at load with human-readable errors; enforce
cross-field invariants here so bad config can never reach a module.
"""

from __future__ import annotations

from datetime import time
from decimal import Decimal
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from athena.domain.enums import DecisionType, Direction


class _Strict(BaseModel):
    """Common base: unknown keys are errors (typos must fail loudly)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="before")
    @classmethod
    def _drop_meta(cls, values: object) -> object:
        if isinstance(values, dict):
            return {k: v for k, v in values.items() if k != "_meta"}
        return values


class PathsConfig(_Strict):
    db: str
    logs: str
    exports: str


class LoggingConfig(_Strict):
    level: str = "INFO"
    retention_days: int = Field(ge=1, default=90)

    @field_validator("level")
    @classmethod
    def _valid_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR"}
        if v.upper() not in allowed:
            raise ValueError(f"logging.level must be one of {sorted(allowed)}, got '{v}'")
        return v.upper()


class BaseConfig(_Strict):
    paths: PathsConfig
    logging: LoggingConfig
    refresh_interval_minutes: int = Field(ge=1, le=120)
    active_profile: str
    features: dict[str, bool]
    performance_budgets_seconds: dict[str, float]

    @field_validator("performance_budgets_seconds")
    @classmethod
    def _positive_budgets(cls, v: dict[str, float]) -> dict[str, float]:
        bad = {k: s for k, s in v.items() if s <= 0}
        if bad:
            raise ValueError(f"performance budgets must be positive seconds: {bad}")
        return v


class SessionsConfig(_Strict):
    preopen_start: time
    preopen_end: time
    open: time
    close: time

    @model_validator(mode="after")
    def _ordered(self) -> SessionsConfig:
        if not (self.preopen_start < self.preopen_end <= self.open < self.close):
            raise ValueError(
                "market sessions must satisfy preopen_start < preopen_end <= open < close, got "
                f"{self.preopen_start}, {self.preopen_end}, {self.open}, {self.close}"
            )
        return self


class MarketConfig(_Strict):
    exchange: str
    timezone: str
    sessions: SessionsConfig
    circuit_bands_pct: list[int]
    series: list[str]
    tick_size_default: Decimal

    @field_validator("circuit_bands_pct")
    @classmethod
    def _bands(cls, v: list[int]) -> list[int]:
        if not v or v != sorted(v) or any(b <= 0 or b > 100 for b in v):
            raise ValueError(f"circuit_bands_pct must be ascending percentages in 1..100, got {v}")
        return v


class NoTradeConfig(_Strict):
    min_market_health: int = Field(ge=0, le=100)
    block_on_stale_data: bool = True


class RiskConfig(_Strict):
    max_daily_loss_pct: float = Field(gt=0, le=100)
    per_trade_risk_pct: float = Field(gt=0, le=100)
    max_consecutive_losses: int = Field(ge=1)
    max_decisions_per_day: int = Field(ge=1)
    no_trade: NoTradeConfig

    @model_validator(mode="after")
    def _risk_invariants(self) -> RiskConfig:
        if self.per_trade_risk_pct > self.max_daily_loss_pct:
            raise ValueError(
                f"per_trade_risk_pct ({self.per_trade_risk_pct}) must be <= "
                f"max_daily_loss_pct ({self.max_daily_loss_pct}) — one trade may not "
                "exceed the daily loss budget"
            )
        return self


class CapitalConfig(_Strict):
    total_capital: Decimal = Field(gt=0)
    reserved_pct: float = Field(ge=0, lt=100)
    max_capital_per_position_pct: float = Field(gt=0, le=100)
    max_capital_per_sector_pct: float = Field(gt=0, le=100)

    @model_validator(mode="after")
    def _capital_invariants(self) -> CapitalConfig:
        if self.max_capital_per_position_pct > self.max_capital_per_sector_pct:
            raise ValueError(
                f"max_capital_per_position_pct ({self.max_capital_per_position_pct}) must be <= "
                f"max_capital_per_sector_pct ({self.max_capital_per_sector_pct})"
            )
        return self


class RegimeConfig(_Strict):
    gap_pct_threshold: float = Field(gt=0)
    high_volatility_vix: float = Field(gt=0)
    low_volatility_vix: float = Field(gt=0)
    trend_ma_fast: int = Field(ge=2)
    trend_ma_slow: int = Field(ge=3)
    market_health_floor: int = Field(ge=0, le=100)
    sector_health_floor: int = Field(ge=0, le=100)

    @model_validator(mode="after")
    def _regime_invariants(self) -> RegimeConfig:
        if self.low_volatility_vix >= self.high_volatility_vix:
            raise ValueError(
                f"low_volatility_vix ({self.low_volatility_vix}) must be < "
                f"high_volatility_vix ({self.high_volatility_vix})"
            )
        if self.trend_ma_fast >= self.trend_ma_slow:
            raise ValueError(
                f"trend_ma_fast ({self.trend_ma_fast}) must be < trend_ma_slow ({self.trend_ma_slow})"
            )
        return self


class UniverseConfig(_Strict):
    max_universe_size: int = Field(ge=1)
    min_avg_daily_volume: int = Field(ge=0)
    min_trading_history_days: int = Field(ge=1)
    supported_series: list[str]
    eligible_exchanges: list[str]
    min_history_completeness: float = Field(gt=0, le=1)
    include_index_constituents: list[str]
    custom_symbols: list[str]

    @field_validator("supported_series", "eligible_exchanges")
    @classmethod
    def _non_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("must list at least one entry")
        return v


class IndicatorsConfig(_Strict):
    versions: dict[str, str]
    params: dict[str, dict[str, int]]

    @model_validator(mode="after")
    def _params_have_versions(self) -> IndicatorsConfig:
        missing = set(self.params) - set(self.versions)
        if missing:
            raise ValueError(f"indicators with params but no version (F-13): {sorted(missing)}")
        return self


class TradingWindow(_Strict):
    start: time
    end: time

    @model_validator(mode="after")
    def _ordered(self) -> TradingWindow:
        if self.start >= self.end:
            raise ValueError(f"trading window start ({self.start}) must be < end ({self.end})")
        return self


class SizingConfig(_Strict):
    method: str
    risk_per_trade_pct: float = Field(gt=0, le=100)


class ProfileConfig(_Strict):
    name: str
    version: str
    indicators: list[str]
    weights: dict[str, int]
    risk_overrides: dict[str, float]
    trading_windows: list[TradingWindow]
    sizing: SizingConfig

    @field_validator("weights")
    @classmethod
    def _weights_sum_100(cls, v: dict[str, int]) -> dict[str, int]:
        total = sum(v.values())
        if total != 100:
            raise ValueError(
                f"profile weights must sum to 100 for decomposable scores, got {total}: {v}"
            )
        if any(w < 0 for w in v.values()):
            raise ValueError(f"profile weights must be >= 0: {v}")
        return v

    @field_validator("trading_windows")
    @classmethod
    def _at_least_one_window(cls, v: list[TradingWindow]) -> list[TradingWindow]:
        if not v:
            raise ValueError("profile must define at least one trading window")
        return v


class AthenaConfig(_Strict):
    """The fully-validated configuration tree for one run."""

    base: BaseConfig
    market: MarketConfig
    risk: RiskConfig
    capital: CapitalConfig
    regime: RegimeConfig
    universe: UniverseConfig
    indicators: IndicatorsConfig
    profile: ProfileConfig

    @model_validator(mode="after")
    def _cross_file_invariants(self) -> AthenaConfig:
        # Profile indicators must exist in indicators.json (versioned, F-13).
        unknown = set(self.profile.indicators) - set(self.indicators.versions)
        if unknown:
            raise ValueError(
                f"profile '{self.profile.name}' references unversioned indicators: "
                f"{sorted(unknown)} — add them to indicators.json"
            )
        # Trading windows must lie within market session hours.
        s = self.market.sessions
        for w in self.profile.trading_windows:
            if w.start < s.open or w.end > s.close:
                raise ValueError(
                    f"profile trading window {w.start}-{w.end} is outside market session "
                    f"{s.open}-{s.close}"
                )
        # No-trade market-health floor must not exceed regime floor semantics.
        if self.risk.no_trade.min_market_health > 100:
            raise ValueError("risk.no_trade.min_market_health must be <= 100")
        # Profile risk overrides may not weaken the daily loss budget.
        override = self.profile.risk_overrides.get("per_trade_risk_pct")
        if override is not None and override > self.risk.max_daily_loss_pct:
            raise ValueError(
                f"profile risk override per_trade_risk_pct ({override}) exceeds "
                f"max_daily_loss_pct ({self.risk.max_daily_loss_pct})"
            )
        return self


class ProviderCapabilitiesConfig(_Strict):
    timeframes: list[str]
    max_history_days: int = Field(ge=1)
    supports_quotes: bool
    supports_market_snapshot: bool

    @field_validator("timeframes")
    @classmethod
    def _known_unique_timeframes(cls, v: list[str]) -> list[str]:
        allowed = {"1m", "5m", "15m", "1d"}
        unknown = [t for t in v if t not in allowed]
        if unknown:
            raise ValueError(f"unknown timeframes {unknown}; allowed: {sorted(allowed)}")
        if len(set(v)) != len(v):
            raise ValueError(f"duplicate timeframes: {v}")
        if "1d" not in v:
            raise ValueError("a provider must serve daily ('1d') candles (Phase 1 baseline)")
        return v


class FileProviderConfig(_Strict):
    """Settings for the file-based provider (M1.2). All paths are relative to data_root."""

    data_root: str
    instruments_file: str
    daily_dir: str
    intraday_dir: str
    quotes_file: str
    snapshot_file: str
    capabilities: ProviderCapabilitiesConfig


class FreshnessConfig(_Strict):
    max_trading_days_behind: int = Field(ge=0)
    intraday_max_minutes_behind: int = Field(gt=0)


class GapConfig(_Strict):
    daily_enabled: bool
    intraday_enabled: bool


class ValidationConfig(_Strict):
    """Validation-layer thresholds (M1.3)."""

    freshness: FreshnessConfig
    gaps: GapConfig


class IngestionConfig(_Strict):
    """Live ingest cycle settings (M10.1). Provider-agnostic; DD-1 broker unbound."""

    provider: Literal["file"] = "file"
    timeframes: list[str] = Field(default_factory=lambda: ["5m"])
    lookback_minutes: int = Field(default=30, ge=1, le=1440)
    lookback_days: int = Field(default=5, ge=1, le=365)
    include_daily: bool = True
    include_quotes: bool = True
    validate_gaps: bool = False
    skip_existing: bool = True
    quarantine_on_failure: bool = True
    instrument_ids: list[str] = Field(default_factory=list)

    @field_validator("timeframes")
    @classmethod
    def _known_unique_intraday(cls, v: list[str]) -> list[str]:
        allowed = {"1m", "5m", "15m"}
        if not v:
            raise ValueError("ingestion.timeframes must declare at least one intraday timeframe")
        unknown = [t for t in v if t not in allowed]
        if unknown:
            raise ValueError(f"unknown intraday timeframes {unknown}; allowed: {sorted(allowed)}")
        if len(set(v)) != len(v):
            raise ValueError(f"duplicate timeframes: {v}")
        return v


class BreadthCfg(_Strict):
    strong_ratio: float = Field(gt=0, lt=1)
    weak_ratio: float = Field(gt=0, lt=1)

    @model_validator(mode="after")
    def _ordered(self) -> BreadthCfg:
        if self.weak_ratio >= self.strong_ratio:
            raise ValueError(
                f"breadth weak_ratio ({self.weak_ratio}) must be < strong_ratio ({self.strong_ratio})")
        return self


class MomentumCfg(_Strict):
    period: int = Field(ge=1)
    healthy_pct: float = Field(gt=0)


class TrendQualityCfg(_Strict):
    window: int = Field(ge=2)
    strong_consistency: float = Field(gt=0, le=1)
    weak_consistency: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def _ordered(self) -> TrendQualityCfg:
        if self.weak_consistency >= self.strong_consistency:
            raise ValueError(
                f"trend weak_consistency ({self.weak_consistency}) must be < "
                f"strong_consistency ({self.strong_consistency})")
        return self


class VolatilityHealthCfg(_Strict):
    calm_vix: float = Field(gt=0)
    elevated_vix: float = Field(gt=0)

    @model_validator(mode="after")
    def _ordered(self) -> VolatilityHealthCfg:
        if self.calm_vix >= self.elevated_vix:
            raise ValueError(
                f"volatility calm_vix ({self.calm_vix}) must be < elevated_vix ({self.elevated_vix})")
        return self


class MarketHealthConfig(_Strict):
    """Market Health Engine thresholds (M2.2)."""

    breadth: BreadthCfg
    momentum: MomentumCfg
    trend_quality: TrendQualityCfg
    volatility: VolatilityHealthCfg


class SectorTrendCfg(_Strict):
    ma_fast: int = Field(ge=2)
    ma_slow: int = Field(ge=3)

    @model_validator(mode="after")
    def _ordered(self) -> SectorTrendCfg:
        if self.ma_fast >= self.ma_slow:
            raise ValueError(f"sector ma_fast ({self.ma_fast}) must be < ma_slow ({self.ma_slow})")
        return self


class SectorVolatilityCfg(_Strict):
    window: int = Field(ge=2)
    calm_pct: float = Field(gt=0)
    elevated_pct: float = Field(gt=0)

    @model_validator(mode="after")
    def _ordered(self) -> SectorVolatilityCfg:
        if self.calm_pct >= self.elevated_pct:
            raise ValueError(
                f"sector calm_pct ({self.calm_pct}) must be < elevated_pct ({self.elevated_pct})")
        return self


class SectorHealthConfig(_Strict):
    """Sector Health Engine thresholds (M2.3)."""

    trend: SectorTrendCfg
    breadth: BreadthCfg
    momentum: MomentumCfg
    volatility: SectorVolatilityCfg


class ScoringWeightsCfg(_Strict):
    trend: int = Field(ge=0)
    momentum: int = Field(ge=0)
    market_quality: int = Field(ge=0)
    sector_quality: int = Field(ge=0)
    liquidity: int = Field(ge=0)
    technical_structure: int = Field(ge=0)

    @model_validator(mode="after")
    def _sum_100(self) -> ScoringWeightsCfg:
        total = (self.trend + self.momentum + self.market_quality
                 + self.sector_quality + self.liquidity + self.technical_structure)
        if total != 100:
            raise ValueError(f"scoring weights must sum to 100, got {total}")
        return self


class RsiScoringCfg(_Strict):
    strong: float = Field(gt=0, lt=100)
    weak: float = Field(gt=0, lt=100)
    strong_points: int = Field(ge=0, le=100)
    mid_points: int = Field(ge=0, le=100)
    weak_points: int = Field(ge=0, le=100)

    @model_validator(mode="after")
    def _ordered(self) -> RsiScoringCfg:
        if self.weak >= self.strong:
            raise ValueError(f"rsi weak ({self.weak}) must be < strong ({self.strong})")
        return self


class AdxScoringCfg(_Strict):
    strong: float = Field(gt=0)
    bonus: int = Field(ge=0, le=100)


class LiquidityScoringCfg(_Strict):
    min_volume_ma: int = Field(ge=0)
    ok_points: int = Field(ge=0, le=100)
    low_points: int = Field(ge=0, le=100)


class TechnicalScoringCfg(_Strict):
    above_ma_points: int = Field(ge=0, le=100)
    below_ma_points: int = Field(ge=0, le=100)
    macd_pos_bonus: int = Field(ge=0, le=100)


class ScoringConfig(_Strict):
    """Scoring Engine configuration (M3.3). All contributions are config-driven."""

    weights: ScoringWeightsCfg
    label_points: dict[str, int]
    rsi: RsiScoringCfg
    adx: AdxScoringCfg
    liquidity: LiquidityScoringCfg
    technical: TechnicalScoringCfg

    @field_validator("label_points")
    @classmethod
    def _points_in_range(cls, v: dict[str, int]) -> dict[str, int]:
        bad = {k: p for k, p in v.items() if not 0 <= p <= 100}
        if bad:
            raise ValueError(f"label_points must be within 0..100: {bad}")
        return v


class ConfidenceWeightsCfg(_Strict):
    evidence_completeness: int = Field(ge=0)
    data_freshness: int = Field(ge=0)
    indicator_availability: int = Field(ge=0)
    cross_engine_agreement: int = Field(ge=0)
    unknown_ratio: int = Field(ge=0)
    consistency: int = Field(ge=0)

    @model_validator(mode="after")
    def _sum_100(self) -> ConfidenceWeightsCfg:
        total = (self.evidence_completeness + self.data_freshness
                 + self.indicator_availability + self.cross_engine_agreement
                 + self.unknown_ratio + self.consistency)
        if total != 100:
            raise ValueError(f"confidence weights must sum to 100, got {total}")
        return self


class ConfidenceLevelsCfg(_Strict):
    low_below: int = Field(ge=0, le=100)
    high_at_or_above: int = Field(ge=0, le=100)

    @model_validator(mode="after")
    def _ordered(self) -> ConfidenceLevelsCfg:
        if self.low_below >= self.high_at_or_above:
            raise ValueError(
                f"low_below ({self.low_below}) must be < high_at_or_above ({self.high_at_or_above})")
        return self


class ConsistencyCfg(_Strict):
    divergence_gap: int = Field(ge=1, le=100)
    contradiction_penalty: int = Field(ge=0, le=100)


class ConfidenceConfig(_Strict):
    """Confidence Engine configuration (M3.4)."""

    weights: ConfidenceWeightsCfg
    levels: ConfidenceLevelsCfg
    consistency: ConsistencyCfg


class RiskWeightsCfg(_Strict):
    volatility_risk: int = Field(ge=0)
    liquidity_risk: int = Field(ge=0)
    gap_risk: int = Field(ge=0)
    event_risk: int = Field(ge=0)
    market_environment_risk: int = Field(ge=0)
    concentration_indicator: int = Field(ge=0)

    @model_validator(mode="after")
    def _sum_100(self) -> RiskWeightsCfg:
        total = (self.volatility_risk + self.liquidity_risk + self.gap_risk + self.event_risk
                 + self.market_environment_risk + self.concentration_indicator)
        if total != 100:
            raise ValueError(f"risk weights must sum to 100, got {total}")
        return self


class RiskLevelsCfg(_Strict):
    low_below: int = Field(ge=0, le=100)
    high_at_or_above: int = Field(ge=0, le=100)

    @model_validator(mode="after")
    def _ordered(self) -> RiskLevelsCfg:
        if self.low_below >= self.high_at_or_above:
            raise ValueError(
                f"low_below ({self.low_below}) must be < high_at_or_above ({self.high_at_or_above})")
        return self


class RiskLiquidityCfg(_Strict):
    min_volume_ma: int = Field(ge=0)
    low_liquidity_risk: int = Field(ge=0, le=100)
    ok_liquidity_risk: int = Field(ge=0, le=100)


class RiskEventCfg(_Strict):
    expiry_risk: int = Field(ge=0, le=100)
    event_risk: int = Field(ge=0, le=100)
    normal_risk: int = Field(ge=0, le=100)


class RiskConcentrationCfg(_Strict):
    min_universe_size: int = Field(ge=1)
    concentrated_risk: int = Field(ge=0, le=100)
    diversified_risk: int = Field(ge=0, le=100)


class RiskAssessmentConfig(_Strict):
    """Risk Engine configuration (M3.5). Descriptive exposure only, not no-trade rules."""

    weights: RiskWeightsCfg
    levels: RiskLevelsCfg
    volatility_points: dict[str, int]
    gap_points: dict[str, int]
    liquidity: RiskLiquidityCfg
    event: RiskEventCfg
    market_env_points: dict[str, int]
    concentration: RiskConcentrationCfg

    @field_validator("volatility_points", "gap_points", "market_env_points")
    @classmethod
    def _points_in_range(cls, v: dict[str, int]) -> dict[str, int]:
        bad = {k: p for k, p in v.items() if not 0 <= p <= 100}
        if bad:
            raise ValueError(f"risk points must be within 0..100: {bad}")
        return v


class DecisionThresholdsCfg(_Strict):
    min_composite_for_trade: int = Field(ge=0, le=100)
    watch_composite: int = Field(ge=0, le=100)
    min_confidence_for_trade: int = Field(ge=0, le=100)
    max_risk_for_trade: int = Field(ge=0, le=100)
    min_evidence_completeness: float = Field(ge=0, le=1)
    market_floor: int = Field(ge=0, le=100)

    @model_validator(mode="after")
    def _ordered(self) -> DecisionThresholdsCfg:
        if self.watch_composite > self.min_composite_for_trade:
            raise ValueError(
                f"watch_composite ({self.watch_composite}) must be <= "
                f"min_composite_for_trade ({self.min_composite_for_trade})")
        return self


class DecisionPlanCfg(_Strict):
    atr_stop_multiple: float = Field(gt=0)
    atr_target_multiple: float = Field(gt=0)
    default_units: int = Field(ge=1)
    validity_hours: int = Field(ge=1)


class DecisionConfig(_Strict):
    """Decision Engine configuration (M3.6). Deterministic gate + policy thresholds."""

    thresholds: DecisionThresholdsCfg
    plan: DecisionPlanCfg


class WatchlistDecisionRuleCfg(_Strict):
    """Membership by the instrument's current decision type (M4.3)."""

    type: Literal["decision_in"]
    decisions: list[str] = Field(min_length=1)

    @field_validator("decisions")
    @classmethod
    def _known_decisions(cls, v: list[str]) -> list[str]:
        valid = {d.value for d in DecisionType}
        bad = [d for d in v if d not in valid]
        if bad:
            raise ValueError(f"unknown decision type(s): {bad}")
        return v


class WatchlistTrendRuleCfg(_Strict):
    """Membership by decision-strength change vs the previous scan (M4.3)."""

    type: Literal["trend"]
    direction: Literal["improving", "weakening"]


class WatchlistDefCfg(_Strict):
    """One named watchlist and the rule that governs membership (M4.3)."""

    name: str = Field(min_length=1)
    rule: WatchlistDecisionRuleCfg | WatchlistTrendRuleCfg = Field(discriminator="type")


class WatchlistConfig(_Strict):
    """Watchlist Manager configuration (M4.3). Classification is config-driven only."""

    decision_rank: dict[str, int]
    watchlists: list[WatchlistDefCfg] = Field(min_length=1)

    @field_validator("decision_rank")
    @classmethod
    def _known_ranks(cls, v: dict[str, int]) -> dict[str, int]:
        valid = {d.value for d in DecisionType}
        bad = [k for k in v if k not in valid]
        if bad:
            raise ValueError(f"decision_rank has unknown decision type(s): {bad}")
        return v

    @model_validator(mode="after")
    def _consistent(self) -> WatchlistConfig:
        names = [w.name for w in self.watchlists]
        dupes = sorted({n for n in names if names.count(n) > 1})
        if dupes:
            raise ValueError(f"watchlist names must be unique: {dupes}")
        if any(isinstance(w.rule, WatchlistTrendRuleCfg) for w in self.watchlists) \
                and not self.decision_rank:
            raise ValueError("decision_rank must be non-empty when a trend rule is used")
        return self


class StrategyRuleCfg(_Strict):
    """Declarative selection policy for one strategy (M4.4).

    All filters are optional; a strategy matches a completed decision when every
    present filter is satisfied. Thresholds compare against values already
    produced by the analytical core — a threshold set against an UNKNOWN value
    never matches (no fabricated defaults).
    """

    enabled: bool = True
    decisions: list[str] = Field(default_factory=list)
    direction: str | None = None
    watchlists_any: list[str] = Field(default_factory=list)
    min_score: int | None = Field(default=None, ge=0, le=100)
    min_confidence: int | None = Field(default=None, ge=0, le=100)
    max_risk: int | None = Field(default=None, ge=0, le=100)

    @field_validator("decisions")
    @classmethod
    def _known_decisions(cls, v: list[str]) -> list[str]:
        valid = {d.value for d in DecisionType}
        bad = [d for d in v if d not in valid]
        if bad:
            raise ValueError(f"unknown decision type(s): {bad}")
        return v

    @field_validator("direction")
    @classmethod
    def _known_direction(cls, v: str | None) -> str | None:
        valid = {d.value for d in Direction}
        if v is not None and v not in valid:
            raise ValueError(f"unknown direction: {v}")
        return v


class StrategyConfig(_Strict):
    """Strategy Framework configuration (M4.4). One rule per strategy id."""

    strategies: dict[str, StrategyRuleCfg]

    @field_validator("strategies")
    @classmethod
    def _non_empty(cls, v: dict[str, StrategyRuleCfg]) -> dict[str, StrategyRuleCfg]:
        if not v:
            raise ValueError("strategy config must define at least one strategy")
        return v


class BacktestConfig(_Strict):
    """Backtesting Engine configuration (M4.5). Replay coordination only."""

    continue_on_error: bool = True
    carry_watchlist: bool = True


class AnalyticsConfig(_Strict):
    """Reporting & Analytics configuration (M4.6). Presentation + aggregation only.

    ``confidence_levels`` / ``risk_levels`` fix the display order of the
    aggregated distributions; ``include_unknown`` controls whether the UNKNOWN
    bucket is reported.
    """

    include_unknown: bool = True
    confidence_levels: list[str] = Field(default_factory=lambda: ["LOW", "MEDIUM", "HIGH"])
    risk_levels: list[str] = Field(default_factory=lambda: ["LOW", "MEDIUM", "HIGH"])

    @field_validator("confidence_levels", "risk_levels")
    @classmethod
    def _non_empty_upper(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("level list must be non-empty")
        bad = [x for x in v if x != x.upper() or not x]
        if bad:
            raise ValueError(f"levels must be non-empty upper-case: {bad}")
        return v


class PremarketScheduleConfig(_Strict):
    """Once-per-trading-day premarket dry-run window (Blueprint §8.1)."""

    enabled: bool = True
    run_at: time = time(8, 15)


class RefreshScheduleConfig(_Strict):
    """Intraday refresh cadence (Blueprint §8.2). ``interval_minutes`` None →
    use ``base.refresh_interval_minutes``."""

    enabled: bool = True
    interval_minutes: int | None = Field(default=None, ge=1, le=120)


class SchedulingConfig(_Strict):
    """Scheduling Framework configuration (M4.7 + M10.2 cadence).

    Coordination only — no embedded cron library, no cloud scheduling.
    Premarket/refresh walls drive ``athena cycle`` / due-trigger evaluation;
    external launchd/cron may invoke the CLI (ATHENA-001 O-2).
    """

    record_history: bool = True
    premarket: PremarketScheduleConfig = Field(default_factory=PremarketScheduleConfig)
    refresh: RefreshScheduleConfig = Field(default_factory=RefreshScheduleConfig)


class PortfolioConfig(_Strict):
    """Portfolio Engine configuration (P5.1). State tracking only —
    no market analysis, no position sizing, no order placement."""

    initial_cash: Decimal = Decimal("1000000.00")
    currency: str = "INR"
    allow_short: bool = False
    record_history: bool = True

    @field_validator("initial_cash")
    @classmethod
    def _positive_cash(cls, v: Decimal) -> Decimal:
        if v < Decimal("0"):
            raise ValueError("initial_cash must be >= 0")
        return v


class AllocationModel(str, Enum):
    FIXED_AMOUNT = "FIXED_AMOUNT"
    FIXED_PERCENTAGE = "FIXED_PERCENTAGE"
    EQUAL_WEIGHT = "EQUAL_WEIGHT"


class AllocationConfig(_Strict):
    """Capital Allocation Engine configuration (P5.2). Allocation policy only —
    no position sizing, no order execution."""

    default_model: AllocationModel = AllocationModel.FIXED_PERCENTAGE
    fixed_amount: Decimal = Decimal("100000.00")
    fixed_percentage: Decimal = Decimal("10.0")
    max_opportunities: int = 5
    min_cash_reserve_pct: Decimal = Decimal("20.0")
    record_history: bool = True

    @field_validator("fixed_amount", "fixed_percentage", "min_cash_reserve_pct")
    @classmethod
    def _positive_decimal(cls, v: Decimal) -> Decimal:
        if v < Decimal("0"):
            raise ValueError("Decimal allocation values must be >= 0")
        return v


class SizingModel(str, Enum):
    WHOLE_SHARE = "WHOLE_SHARE"
    FRACTIONAL = "FRACTIONAL"


class RoundingMode(str, Enum):
    ROUND_DOWN = "ROUND_DOWN"
    ROUND_UP = "ROUND_UP"


class SizingConfig(_Strict):
    """Position Sizing Engine configuration (P5.3). Quantity calculation only —
    no order placement, no broker execution."""

    default_model: SizingModel = SizingModel.WHOLE_SHARE
    default_rounding: RoundingMode = RoundingMode.ROUND_DOWN
    decimal_precision: int = 4
    record_history: bool = True

    @field_validator("decimal_precision")
    @classmethod
    def _non_negative_precision(cls, v: int) -> int:
        if v < 0:
            raise ValueError("decimal_precision must be >= 0")
        return v


class OrderAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class OrderPlanningConfig(_Strict):
    """Order Planning Engine configuration (P5.4). Execution instruction preparation only —
    no broker communication, no order placement."""

    default_order_type: OrderType = OrderType.LIMIT
    batch_by_action: bool = True
    max_orders_per_batch: int = 10
    record_history: bool = True

    @field_validator("max_orders_per_batch")
    @classmethod
    def _positive_batch_size(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("max_orders_per_batch must be > 0")
        return v


class TimeInForce(str, Enum):
    DAY = "DAY"
    IOC = "IOC"
    FOK = "FOK"
    GTC = "GTC"


class BrokerConfig(_Strict):
    """Broker Abstraction Layer configuration (P5.5). Integration contract definition only —
    no live SDKs, no network communication."""

    default_broker_id: str = "paper_broker"
    default_time_in_force: TimeInForce = TimeInForce.DAY
    validate_capabilities: bool = True
    record_history: bool = True


class OrderLifecycleState(str, Enum):
    CREATED = "CREATED"
    ACCEPTED = "ACCEPTED"
    SUBMITTED = "SUBMITTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class ExecutionConfig(_Strict):
    """Order Lifecycle Engine configuration (P5.6). Execution state tracking only —
    no live polling, no broker SDKs."""

    allow_partial_fills: bool = True
    enforce_strict_transitions: bool = True
    record_history: bool = True


class PortfolioAnalyticsConfig(_Strict):
    """Portfolio Analytics Engine configuration (P5.7). Performance calculation only —
    no live dashboards or forecasting."""

    initial_capital: Decimal = Decimal("1000000.00")
    risk_free_rate_pct: Decimal = Decimal("6.00")
    record_history: bool = True

    @field_validator("initial_capital", "risk_free_rate_pct")
    @classmethod
    def _non_negative_decimal(cls, v: Decimal) -> Decimal:
        if v < Decimal("0"):
            raise ValueError("Decimal values must be >= 0")
        return v


class ReportType(str, Enum):
    PORTFOLIO = "PORTFOLIO"
    EXECUTION = "EXECUTION"
    ALLOCATION = "ALLOCATION"
    ANALYTICS = "ANALYTICS"
    AUDIT = "AUDIT"


class ReportingFrameworkConfig(_Strict):
    """Reporting Framework configuration (P6.1). Read-only report generation —
    no state mutation."""

    default_format: str = "text"
    include_text_rendering: bool = True
    record_history: bool = True


class DashboardConfig(_Strict):
    """Dashboard & Snapshot Engine configuration (P6.2). Read-only derived operational views —
    no UI rendering or state mutation."""

    default_theme: str = "dark"
    include_text_rendering: bool = True
    record_history: bool = True


class ExplanationDomain(str, Enum):
    DECISION = "DECISION"
    PORTFOLIO = "PORTFOLIO"
    ALLOCATION = "ALLOCATION"
    SIZING = "SIZING"
    ORDER_PLANNING = "ORDER_PLANNING"
    BROKER_TRANSLATION = "BROKER_TRANSLATION"
    LIFECYCLE = "LIFECYCLE"
    ANALYTICS = "ANALYTICS"
    REPORTING = "REPORTING"


class ExplainabilityConfig(_Strict):
    """Explainability Engine configuration (P6.3). Read-only rationale generation —
    no state mutation, no LLMs."""

    detail_level: str = "detailed"
    include_facts: bool = True
    record_history: bool = True


class TimelineDomain(str, Enum):
    DECISION = "DECISION"
    PORTFOLIO = "PORTFOLIO"
    ALLOCATION = "ALLOCATION"
    SIZING = "SIZING"
    ORDER_PLANNING = "ORDER_PLANNING"
    BROKER_TRANSLATION = "BROKER_TRANSLATION"
    LIFECYCLE = "LIFECYCLE"
    ANALYTICS = "ANALYTICS"
    REPORTING = "REPORTING"
    DASHBOARD = "DASHBOARD"
    EXPLAINABILITY = "EXPLAINABILITY"


class TimelineConfig(_Strict):
    """Timeline & Audit Engine configuration (P6.4). Read-only timeline reconstruction —
    no state mutation."""

    enforce_strict_causal_ordering: bool = True
    record_history: bool = True


class MonitoringDomain(str, Enum):
    SCHEDULER = "SCHEDULER"
    WORKFLOW = "WORKFLOW"
    PORTFOLIO = "PORTFOLIO"
    EXECUTION = "EXECUTION"
    ANALYTICS = "ANALYTICS"
    REPORTING = "REPORTING"
    DASHBOARD = "DASHBOARD"
    EXPLAINABILITY = "EXPLAINABILITY"
    TIMELINE = "TIMELINE"
    OVERALL = "OVERALL"


class MonitoringConfig(_Strict):
    """Operational Monitoring Engine configuration (P6.5). Read-only platform health observation —
    no state mutation, no auto-remediation."""

    fail_on_missing_artifacts: bool = False
    record_history: bool = True


class ExportFormat(str, Enum):
    JSON = "JSON"
    MARKDOWN = "MARKDOWN"
    TEXT = "TEXT"
    CSV = "CSV"


class ExportConfig(_Strict):
    """Export & Presentation Layer configuration (P6.6). Read-only presentation format adaptation —
    no state mutation."""

    default_format: ExportFormat = ExportFormat.JSON
    pretty_print_json: bool = True
    record_history: bool = True


class WorkspaceConfig(_Strict):
    """Unified Intelligence Workspace configuration (P6.7). Read-only intelligence composition surface —
    no state mutation."""

    include_unified_summary: bool = True
    record_history: bool = True


class OrchestrationConfig(_Strict):
    """Generic Pipeline Infrastructure configuration (P7.1). Read-only stage execution framework."""

    stop_on_stage_failure: bool = True
    record_history: bool = True

















class Holiday(_Strict):
    date: str
    name: str


class SpecialSession(_Strict):
    date: str
    type: str
    name: str
    timings_note: str | None = None
    open: time | None = None
    close: time | None = None


class HolidaysFile(_Strict):
    years: list[int]
    holidays: list[Holiday]
    special_sessions: list[SpecialSession]


class ExpiriesFile(_Strict):
    weekly: list[str]
    monthly: list[str]


class EventItem(_Strict):
    date: str
    kind: str
    name: str


class EventsFile(_Strict):
    events: list[EventItem]
