"""Canonical enumerations (ATHENA-002 §4). Values are stable storage contracts."""

from __future__ import annotations

from enum import Enum, unique


@unique
class Timeframe(str, Enum):
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    D1 = "1d"


@unique
class SessionType(str, Enum):
    NORMAL = "NORMAL"
    WEEKEND = "WEEKEND"
    HOLIDAY = "HOLIDAY"
    MUHURAT = "MUHURAT"
    SPECIAL = "SPECIAL"


@unique
class DecisionType(str, Enum):
    """Canonical decision vocabulary (R-6). Exactly these twelve."""

    TRADE = "TRADE"
    WATCH = "WATCH"
    WAIT = "WAIT"
    NO_TRADE = "NO_TRADE"
    REDUCE_POSITION = "REDUCE_POSITION"
    INCREASE_POSITION = "INCREASE_POSITION"
    PARTIAL_EXIT = "PARTIAL_EXIT"
    FULL_EXIT = "FULL_EXIT"
    AVOID_SECTOR = "AVOID_SECTOR"
    MARKET_CLOSED = "MARKET_CLOSED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    DATA_VALIDATION_FAILED = "DATA_VALIDATION_FAILED"


@unique
class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    NONE = "NONE"


@unique
class EvidenceCategory(str, Enum):
    TECHNICAL = "TECHNICAL"
    PRICE_ACTION = "PRICE_ACTION"
    VOLUME = "VOLUME"
    VWAP = "VWAP"
    PATTERN = "PATTERN"
    SECTOR = "SECTOR"
    BREADTH = "BREADTH"
    NEWS = "NEWS"
    RISK = "RISK"
    PORTFOLIO = "PORTFOLIO"
    AI = "AI"


@unique
class UserAction(str, Enum):
    """Owner's response to a recommendation (R-9)."""

    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    IGNORED = "IGNORED"


@unique
class RunTrigger(str, Enum):
    PREMARKET = "PREMARKET"
    REFRESH = "REFRESH"
    CLOSING = "CLOSING"
    CLOSE = "CLOSE"
    REPLAY = "REPLAY"
    SIMULATE = "SIMULATE"


@unique
class RunStatus(str, Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


@unique
class HealthStatus(str, Enum):
    OK = "OK"
    WARN = "WARN"
    BLOCKED = "BLOCKED"


@unique
class QualityGate(str, Enum):
    """The six decision quality gates (F-12, ATHENA-002 §8.5)."""

    DATA = "DATA"
    EVIDENCE = "EVIDENCE"
    RISK = "RISK"
    EXPLAINABILITY = "EXPLAINABILITY"
    CONFIDENCE = "CONFIDENCE"
    MARKET = "MARKET"
