"""ATHENA canonical domain model (ATHENA-002 §4) — frozen contracts between all modules.

Pure layer: no I/O, no network, no clock reads. Changing any object here is a
reviewed change; removing/renaming a field requires a blueprint amendment (ADR).
"""

from athena.domain.context import ContextDelta, PipelineContext
from athena.domain.decision import (
    CapitalState,
    Decision,
    DecisionJournalEntry,
    DecisionTrace,
    GateResult,
    Portfolio,
    Position,
    RiskEvaluation,
    TraceStage,
    TradeOutcome,
    TradePlan,
)
from athena.domain.enums import (
    DecisionType,
    Direction,
    EvidenceCategory,
    HealthStatus,
    QualityGate,
    RunStatus,
    RunTrigger,
    SessionType,
    Timeframe,
    UserAction,
)
from athena.domain.evidence import (
    ConfidenceAssessment,
    Evidence,
    ExplainabilityReport,
    Score,
    Signal,
)
from athena.domain.health import HealthCheck, SystemHealthReport
from athena.domain.interfaces import (
    InstitutionalFlowProvider,
    IntelligenceModule,
    MarketDataProvider,
    ProviderCapabilities,
    ProviderHealth,
)
from athena.domain.market import (
    CalendarContext,
    CalendarEvent,
    Candle,
    CorporateAction,
    Instrument,
    InstitutionalFlowSession,
    MarketHealthScore,
    MarketSnapshot,
    Quote,
    RegimeAssessment,
    SectorHealthScore,
    SectorSnapshot,
    Universe,
    UniverseMember,
)
from athena.domain.run import ConfigurationSnapshot, RunRecord

__all__ = [
    "CalendarContext", "CalendarEvent", "Candle", "CapitalState", "ConfidenceAssessment",
    "ConfigurationSnapshot", "ContextDelta", "CorporateAction", "Decision",
    "DecisionJournalEntry", "DecisionTrace", "DecisionType", "Direction", "Evidence",
    "EvidenceCategory", "ExplainabilityReport", "GateResult", "HealthCheck", "HealthStatus",
    "Instrument", "InstitutionalFlowProvider", "InstitutionalFlowSession",
    "IntelligenceModule", "MarketDataProvider",
    "MarketHealthScore",
    "MarketSnapshot", "PipelineContext", "Portfolio", "Position", "ProviderCapabilities",
    "ProviderHealth", "QualityGate", "Quote", "RegimeAssessment", "RiskEvaluation",
    "RunRecord", "RunStatus", "RunTrigger", "Score", "SectorHealthScore", "SectorSnapshot",
    "SessionType", "Signal", "SystemHealthReport", "Timeframe", "TraceStage", "TradeOutcome",
    "TradePlan", "Universe", "UniverseMember", "UserAction",
]
