"""Decision report model (M3.7).

An immutable, presentation-only artifact offering both a machine-readable view
(``to_dict``, JSON-safe) and a human-readable view (``to_text``) derived from the
same immutable source. It never modifies, reinterprets, or recalculates any
decision artifact.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class DecisionReport:
    """Faithful, deterministic report of a single decision. Presentation only."""

    decision_id: str
    decision_type: str
    ts: datetime
    machine: Mapping[str, object]
    text: str

    def __post_init__(self) -> None:
        if not self.machine:
            raise ValueError("DecisionReport.machine must be non-empty")
        if not self.text:
            raise ValueError("DecisionReport.text must be non-empty")
        if self.ts.tzinfo is None:
            raise ValueError("DecisionReport.ts must be timezone-aware")
        object.__setattr__(self, "machine", MappingProxyType(dict(self.machine)))

    def to_dict(self) -> dict[str, object]:
        """Machine-readable structured report (deep-copied, JSON-safe)."""
        return json.loads(json.dumps(dict(self.machine)))

    def to_text(self) -> str:
        """Human-readable report."""
        return self.text

    def to_json(self) -> str:
        """Deterministic JSON serialization of the machine-readable report."""
        return json.dumps(dict(self.machine), sort_keys=True, indent=2)
