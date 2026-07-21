"""Pydantic models for every configuration layer (ATHENA-002 §6).

Validation philosophy: fail fast at load with human-readable errors; enforce
cross-field invariants here so bad config can never reach a module.
"""

from __future__ import annotations

from datetime import time
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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
