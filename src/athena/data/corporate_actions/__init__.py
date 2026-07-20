"""Corporate Actions Engine (M1.4).

Provider- and storage-independent. Models splits, bonuses, dividends, and
renames; applies deterministic, explainable back-adjustment producing adjusted
copies of canonical candle datasets. Never fetches, never persists, never
mutates originals.
"""

from athena.data.corporate_actions.engine import CorporateActionsEngine
from athena.data.corporate_actions.evidence import AdjustmentEvidence, AdjustmentResult
from athena.data.corporate_actions.models import (
    AdjustmentStrategy,
    Bonus,
    CorporateActionType,
    Dividend,
    Rename,
    Split,
    parse_action,
)

__all__ = [
    "AdjustmentEvidence",
    "AdjustmentResult",
    "AdjustmentStrategy",
    "Bonus",
    "CorporateActionType",
    "CorporateActionsEngine",
    "Dividend",
    "Rename",
    "Split",
    "parse_action",
]
