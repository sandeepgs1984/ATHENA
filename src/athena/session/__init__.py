"""Session Context (ID-1) — deterministic intraday session/provenance foundation.

Descriptive only: no signals, no gates, no trading interpretation. See
`docs/research/ID-1-*` for the full design rationale.
"""

from athena.session.engine import (
    SessionContextEngine,
    classify_session_phase,
    is_candle_completed,
    latest_completed_candle,
)
from athena.session.models import (
    SessionContext,
    SessionDataQualityStatus,
    SessionPhase,
    TimeframeProvenance,
)

__all__ = [
    "SessionContext",
    "SessionContextEngine",
    "SessionDataQualityStatus",
    "SessionPhase",
    "TimeframeProvenance",
    "classify_session_phase",
    "is_candle_completed",
    "latest_completed_candle",
]
