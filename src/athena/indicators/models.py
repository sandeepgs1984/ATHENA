"""Indicator result types (M3.2).

Immutable measurement objects (not frozen domain §4). Every result is traceable
to its inputs, configuration, and formula. Measurements only — an IndicatorResult
never implies bullishness, bearishness, strength, or weakness.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum, unique
from types import MappingProxyType


@unique
class IndicatorName(str, Enum):
    SMA = "SMA"
    EMA = "EMA"
    RSI = "RSI"
    ATR = "ATR"
    MACD = "MACD"
    ADX = "ADX"
    VOLUME_MA = "VOLUME_MA"


@unique
class IndicatorStatus(str, Enum):
    OK = "OK"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class IndicatorEvidence:
    """The formula and inputs behind a calculation — full traceability."""

    formula: str
    inputs: Mapping[str, str]
    explanation: str

    def __post_init__(self) -> None:
        if not self.formula:
            raise ValueError("IndicatorEvidence.formula is mandatory")
        if not self.explanation:
            raise ValueError("IndicatorEvidence.explanation is mandatory (explainability)")
        object.__setattr__(self, "inputs", MappingProxyType(dict(self.inputs)))


@dataclass(frozen=True, slots=True)
class IndicatorResult:
    """Immutable result of one indicator calculation."""

    name: IndicatorName
    status: IndicatorStatus
    parameters: Mapping[str, int]
    window_used: int
    values: Mapping[str, Decimal]
    evidence: IndicatorEvidence
    ts: datetime

    def __post_init__(self) -> None:
        if self.ts.tzinfo is None:
            raise ValueError("IndicatorResult.ts must be timezone-aware")
        if self.status is IndicatorStatus.OK and not self.values:
            raise ValueError("an OK IndicatorResult must carry at least one value")
        if self.status is IndicatorStatus.UNKNOWN and self.values:
            raise ValueError("an UNKNOWN IndicatorResult must not carry values")
        object.__setattr__(self, "parameters", MappingProxyType(dict(self.parameters)))
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))

    @property
    def is_known(self) -> bool:
        return self.status is IndicatorStatus.OK
