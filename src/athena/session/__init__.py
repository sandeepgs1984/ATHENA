"""Session Context (ID-1) — deterministic intraday session/provenance foundation.

Descriptive only: no signals, no gates, no trading interpretation. See
`docs/research/ID-1-*` for the full design rationale.
"""

from athena.session.engine import (
    SessionContextEngine,
    canonical_slot_candles,
    classify_session_phase,
    completed_candles,
    is_candle_completed,
    latest_completed_candle,
    session_day_start,
    session_open_close_ts,
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
    "canonical_slot_candles",
    "classify_session_phase",
    "completed_candles",
    "is_candle_completed",
    "latest_completed_candle",
    "session_day_start",
    "session_open_close_ts",
]
