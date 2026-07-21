"""Decision Engine result wrapper (M3.6).

The Decision Engine produces the frozen-domain ``Decision`` and ``DecisionTrace``
(ATHENA-002 §4). This module only bundles the two together as one immutable
outcome — it adds no fields to the frozen domain model.
"""

from __future__ import annotations

from dataclasses import dataclass

from athena.domain.decision import Decision, DecisionTrace


@dataclass(frozen=True, slots=True)
class DecisionOutcome:
    """A frozen-domain Decision paired with its complete reasoning trace."""

    decision: Decision
    trace: DecisionTrace

    def __post_init__(self) -> None:
        if self.trace.decision_ref != self.decision.decision_id:
            raise ValueError("DecisionOutcome.trace must reference its decision")
