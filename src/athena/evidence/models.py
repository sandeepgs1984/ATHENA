"""Evidence aggregation result types (M3.1).

The EvidenceBundle is a single immutable graph of provenance-tagged evidence
gathered from approved intelligence. Aggregation only — no scoring, signals, or
decisions. These are decision-intelligence result types (not frozen domain §4).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, unique
from types import MappingProxyType


@unique
class EvidenceSource(str, Enum):
    """The approved intelligence sources the aggregator can gather from."""

    REGIME = "REGIME"
    MARKET_HEALTH = "MARKET_HEALTH"
    SECTOR_HEALTH = "SECTOR_HEALTH"
    UNIVERSE = "UNIVERSE"
    CORPORATE_ACTION = "CORPORATE_ACTION"
    VALIDATION = "VALIDATION"


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    """One atomic piece of evidence with full provenance. Immutable.

    ``payload`` holds the original (frozen) intelligence object, so nothing is
    lost or transformed — the bundle preserves the source evidence verbatim.
    """

    source: EvidenceSource
    kind: str
    reference_id: str
    ts: datetime
    explanation: str
    payload: object

    def __post_init__(self) -> None:
        if not self.kind:
            raise ValueError("EvidenceItem.kind is mandatory")
        if not self.reference_id:
            raise ValueError("EvidenceItem.reference_id is mandatory")
        if not self.explanation:
            raise ValueError("EvidenceItem.explanation is mandatory (explainability)")
        if self.ts.tzinfo is None:
            raise ValueError("EvidenceItem.ts must be timezone-aware")


@dataclass(frozen=True, slots=True)
class EvidenceBundle:
    """Immutable aggregation of all gathered evidence for one point in time."""

    bundle_id: str
    as_of: datetime
    items: tuple[EvidenceItem, ...]
    missing_sources: tuple[str, ...]
    provenance: Mapping[str, int]

    def __post_init__(self) -> None:
        if self.as_of.tzinfo is None:
            raise ValueError("EvidenceBundle.as_of must be timezone-aware")
        object.__setattr__(self, "provenance", MappingProxyType(dict(self.provenance)))

    @property
    def present_sources(self) -> tuple[str, ...]:
        return tuple(sorted({item.source.value for item in self.items}))

    @property
    def is_complete(self) -> bool:
        """True when no required source is missing."""
        return not self.missing_sources

    def by_source(self, source: EvidenceSource) -> tuple[EvidenceItem, ...]:
        return tuple(item for item in self.items if item.source is source)

    def has_source(self, source: EvidenceSource) -> bool:
        return any(item.source is source for item in self.items)
