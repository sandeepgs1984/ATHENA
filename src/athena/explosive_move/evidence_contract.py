"""EM-2 evidence contract: the frozen, versioned manifest of every
feature EM-2 computes. Owner/Chief Architect approved 2026-08-27 (in
principle; contract-correction pass applied: 28 primitives, not 29;
SESSION_STATIC renamed SESSION_INVARIANT with PRIOR_HISTORY /
SESSION_OPEN_CONTEXT provenance subtypes; EVIDENCE_ONLY vs
CANDIDATE_FEATURE classification added; RANGE_COMPRESSION_20 lookback
frozen exactly at 34, not approximated).

This module is pure metadata (no computation, no I/O) -- it exists so
the manifest, the computation modules, and the tests can all reference
the SAME field list and cannot silently drift apart. Any change to a
formula, lookback, cutoff, or UNKNOWN condition is an evidence-contract
change and requires a new ``EVIDENCE_CONTRACT_VERSION``, never a silent
mutation of what a field named ``em2-evidence-v1`` means.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

EVIDENCE_CONTRACT_VERSION = "em2-evidence-v1"

#: Owner-approved starter families (7). Explicitly deferred: relative
#: strength / sector leadership -- would require synchronized historical
#: sector/index evidence and would expand this milestone; not implemented
#: as a conclusion that it's unimportant, purely a scope decision.
DEFERRED_EVIDENCE_FAMILIES = (
    "relative strength vs sector/index",
    "sector leadership rank",
)


class Timing(str, Enum):
    """When a field is computed relative to the 9 accepted checkpoints."""

    #: Computed once per (symbol, session); identical across all 9
    #: checkpoints for that symbol-session.
    SESSION_INVARIANT = "SESSION_INVARIANT"
    #: Computed independently per (symbol, session, checkpoint); may
    #: differ at every checkpoint.
    CHECKPOINT_DYNAMIC = "CHECKPOINT_DYNAMIC"


class Provenance(str, Enum):
    """SESSION_INVARIANT subtype -- not every invariant field comes only
    from prior-session history."""

    #: Derived entirely from admitted daily bars strictly before session T.
    PRIOR_HISTORY = "PRIOR_HISTORY"
    #: Requires session T's own open -- still invariant across all 9
    #: checkpoints because the open is known before the first one (09:20).
    SESSION_OPEN_CONTEXT = "SESSION_OPEN_CONTEXT"
    #: CHECKPOINT_DYNAMIC fields have no session-invariant provenance
    #: subtype; this value marks that dimension not applicable.
    NOT_APPLICABLE = "NOT_APPLICABLE"


class Classification(str, Enum):
    """Whether a field is safe to feed directly into a future predictive
    model, or is raw/scale-dependent evidence kept for explainability and
    replay only. EM-3 may revisit this via evidence, but EM-2 does not
    silently expose every raw numeric field as if it were model-ready."""

    #: Already normalized/relative/bounded; a reasonable candidate input
    #: for a future model, pending EM-3's own signal analysis.
    CANDIDATE_FEATURE = "CANDIDATE_FEATURE"
    #: Raw, scale-dependent (price or volume units) or otherwise an
    #: intermediate value -- kept for explainability/replay, not intended
    #: as a direct model input.
    EVIDENCE_ONLY = "EVIDENCE_ONLY"


@dataclass(frozen=True, slots=True)
class EvidenceField:
    name: str
    family: str
    timing: Timing
    provenance: Provenance
    classification: Classification
    definition: str
    minimum_lookback_sessions: int | None  # None only for fields with no lookback requirement
    unknown_reasons: tuple[str, ...]


# --------------------------------------------------------------------------- #
# SESSION_INVARIANT / PRIOR_HISTORY (13)
# --------------------------------------------------------------------------- #

_PRIOR_HISTORY_FIELDS = (
    EvidenceField(
        "SMA20_REL", "Trend", Timing.SESSION_INVARIANT, Provenance.PRIOR_HISTORY,
        Classification.CANDIDATE_FEATURE,
        "close[T-1] / SMA(20 daily closes through T-1) - 1", 20,
        ("fewer than 20 admitted daily bars strictly before T",),
    ),
    EvidenceField(
        "SMA50_REL", "Trend", Timing.SESSION_INVARIANT, Provenance.PRIOR_HISTORY,
        Classification.CANDIDATE_FEATURE,
        "close[T-1] / SMA(50 daily closes through T-1) - 1", 50,
        ("fewer than 50 admitted daily bars strictly before T",),
    ),
    EvidenceField(
        "SMA20_SLOPE_5", "Trend", Timing.SESSION_INVARIANT, Provenance.PRIOR_HISTORY,
        Classification.CANDIDATE_FEATURE,
        "SMA(20) as of T-1 / SMA(20) as of T-6 - 1 (5-session slope of the 20-session SMA)", 25,
        ("fewer than 25 admitted daily bars strictly before T (20-period SMA series needs >=6 points)",),
    ),
    EvidenceField(
        "ADX14", "Trend", Timing.SESSION_INVARIANT, Provenance.PRIOR_HISTORY,
        Classification.CANDIDATE_FEATURE,
        "canonical Wilder ADX(14) value (trend-strength magnitude, 0-100, direction-agnostic)", 29,
        ("fewer than 29 admitted daily bars strictly before T",),
    ),
    EvidenceField(
        "RSI14", "Momentum", Timing.SESSION_INVARIANT, Provenance.PRIOR_HISTORY,
        Classification.CANDIDATE_FEATURE,
        "canonical Wilder RSI(14) value", 15,
        ("fewer than 15 admitted daily bars strictly before T",),
    ),
    EvidenceField(
        "MACD_HIST", "Momentum", Timing.SESSION_INVARIANT, Provenance.PRIOR_HISTORY,
        Classification.EVIDENCE_ONLY,
        "canonical MACD(12,26,9) histogram value (MACD line minus signal line) -- raw price-unit "
        "scale-dependent, like ATR14; classified EVIDENCE_ONLY by the same principle the owner "
        "applied to ATR14, extending it explicitly rather than silently including it as a candidate",
        35, ("fewer than 35 admitted daily bars strictly before T",),
    ),
    EvidenceField(
        "RETURN_5D", "Momentum", Timing.SESSION_INVARIANT, Provenance.PRIOR_HISTORY,
        Classification.CANDIDATE_FEATURE,
        "close[T-1] / close[T-6] - 1 (trailing 5-session return)", 6,
        ("fewer than 6 admitted daily bars strictly before T",),
    ),
    EvidenceField(
        "RETURN_20D", "Momentum", Timing.SESSION_INVARIANT, Provenance.PRIOR_HISTORY,
        Classification.CANDIDATE_FEATURE,
        "close[T-1] / close[T-21] - 1 (trailing 20-session return)", 21,
        ("fewer than 21 admitted daily bars strictly before T",),
    ),
    EvidenceField(
        "ATR14", "Volatility", Timing.SESSION_INVARIANT, Provenance.PRIOR_HISTORY,
        Classification.EVIDENCE_ONLY,
        "canonical Wilder ATR(14) value (raw price-unit volatility measure)", 15,
        ("fewer than 15 admitted daily bars strictly before T",),
    ),
    EvidenceField(
        "ATR14_NORM", "Volatility", Timing.SESSION_INVARIANT, Provenance.PRIOR_HISTORY,
        Classification.CANDIDATE_FEATURE,
        "ATR14 / close[T-1] (price-normalized volatility)", 15,
        ("ATR14 is UNKNOWN",),
    ),
    EvidenceField(
        "RANGE_COMPRESSION_20", "Volatility", Timing.SESSION_INVARIANT, Provenance.PRIOR_HISTORY,
        Classification.CANDIDATE_FEATURE,
        "ATR14[T-1] / mean(the trailing 20 values of the ATR(14) series ending at and including "
        "T-1's own ATR14 value). Exact contract: atr_series(daily_bars_through_T-1, period=14) "
        "has length len(daily_bars)-14; the denominator is the mean of that series' LAST 20 "
        "elements (T-1's own ATR14 IS one of the 20). Requires len(daily_bars)-14 >= 20.", 34,
        ("fewer than 34 admitted daily bars strictly before T",),
    ),
    EvidenceField(
        "REGIME_TREND", "Regime", Timing.SESSION_INVARIANT, Provenance.PRIOR_HISTORY,
        Classification.CANDIDATE_FEATURE,
        "EM-1c's own point-in-time-safe session regime trend label, joined by session_date "
        "(already T-1-cutoff-safe by that milestone's own contract)", None,
        ("EM-1c's own regime evidence reports TREND_UNKNOWN for this session_date",),
    ),
    EvidenceField(
        "REGIME_VOLATILITY", "Regime", Timing.SESSION_INVARIANT, Provenance.PRIOR_HISTORY,
        Classification.CANDIDATE_FEATURE,
        "EM-1c's own point-in-time-safe session regime volatility label, joined by session_date", None,
        ("EM-1c's own regime evidence reports VOLATILITY_UNKNOWN for this session_date",),
    ),
)

# --------------------------------------------------------------------------- #
# SESSION_INVARIANT / SESSION_OPEN_CONTEXT (2)
# --------------------------------------------------------------------------- #

_SESSION_OPEN_CONTEXT_FIELDS = (
    EvidenceField(
        "GAP_PCT", "Opening", Timing.SESSION_INVARIANT, Provenance.SESSION_OPEN_CONTEXT,
        Classification.CANDIDATE_FEATURE,
        "session_open[T] / close[T-1] - 1. Session T's own open is legitimately known before "
        "the first accepted checkpoint (09:20), so this is invariant across all 9 checkpoints.",
        1, ("no admitted daily bar for T-1",),
    ),
    EvidenceField(
        "REGIME_GAP", "Regime", Timing.SESSION_INVARIANT, Provenance.SESSION_OPEN_CONTEXT,
        Classification.CANDIDATE_FEATURE,
        "EM-1c's own point-in-time-safe session regime gap label (index-level, NIFTY 50 -- "
        "distinct from GAP_PCT, which is this symbol's own gap), joined by session_date", None,
        ("EM-1c's own regime evidence reports GAP_UNKNOWN for this session_date",),
    ),
)

SESSION_INVARIANT_FIELDS = _PRIOR_HISTORY_FIELDS + _SESSION_OPEN_CONTEXT_FIELDS

# --------------------------------------------------------------------------- #
# CHECKPOINT_DYNAMIC (13)
# --------------------------------------------------------------------------- #

CHECKPOINT_DYNAMIC_FIELDS = (
    EvidenceField(
        "CUM_VOLUME_C", "Volume", Timing.CHECKPOINT_DYNAMIC, Provenance.NOT_APPLICABLE,
        Classification.EVIDENCE_ONLY,
        "sum(volume) over session T's M5 candles with ts_open < C", None,
        ("no M5 candles with ts_open < C",),
    ),
    EvidenceField(
        "REL_VOLUME_C", "Volume", Timing.CHECKPOINT_DYNAMIC, Provenance.NOT_APPLICABLE,
        Classification.CANDIDATE_FEATURE,
        "CUM_VOLUME_C / mean(cumulative volume through the same time-of-day C, over the trailing "
        "20 prior admitted sessions that have at least one M5 candle at that time-of-day)", 20,
        ("fewer than 20 prior admitted sessions with comparable-time-of-day volume data",
         "CUM_VOLUME_C is UNKNOWN"),
    ),
    EvidenceField(
        "DIST_FROM_20D_HIGH_C", "Price-location", Timing.CHECKPOINT_DYNAMIC, Provenance.NOT_APPLICABLE,
        Classification.CANDIDATE_FEATURE,
        "price_at_checkpoint(C) / max(daily high over the trailing 20 admitted bars through T-1) - 1", 20,
        ("fewer than 20 admitted daily bars strictly before T", "no candle at exactly C"),
    ),
    EvidenceField(
        "DIST_FROM_20D_LOW_C", "Price-location", Timing.CHECKPOINT_DYNAMIC, Provenance.NOT_APPLICABLE,
        Classification.CANDIDATE_FEATURE,
        "price_at_checkpoint(C) / min(daily low over the trailing 20 admitted bars through T-1) - 1", 20,
        ("fewer than 20 admitted daily bars strictly before T", "no candle at exactly C"),
    ),
    EvidenceField(
        "RANGE_POSITION_20D_C", "Price-location", Timing.CHECKPOINT_DYNAMIC, Provenance.NOT_APPLICABLE,
        Classification.CANDIDATE_FEATURE,
        "(price_at_checkpoint(C) - LOW_20D) / (HIGH_20D - LOW_20D)", 20,
        ("fewer than 20 admitted daily bars strictly before T", "HIGH_20D == LOW_20D", "no candle at exactly C"),
    ),
    EvidenceField(
        "RETURN_FROM_OPEN_C", "Opening", Timing.CHECKPOINT_DYNAMIC, Provenance.NOT_APPLICABLE,
        Classification.CANDIDATE_FEATURE,
        "price_at_checkpoint(C) / session_open[T] - 1", None,
        ("no candle at exactly C",),
    ),
    EvidenceField(
        "RETURN_FROM_PREV_CLOSE_C", "Opening", Timing.CHECKPOINT_DYNAMIC, Provenance.NOT_APPLICABLE,
        Classification.CANDIDATE_FEATURE,
        "price_at_checkpoint(C) / close[T-1] - 1", 1,
        ("no admitted daily bar for T-1", "no candle at exactly C"),
    ),
    EvidenceField(
        "HIGH_SO_FAR_C", "Opening", Timing.CHECKPOINT_DYNAMIC, Provenance.NOT_APPLICABLE,
        Classification.EVIDENCE_ONLY,
        "max(high) over session T's M5 candles with ts_open < C (reuses "
        "event_labels.session_high_so_far unchanged)", None,
        ("no M5 candles with ts_open < C",),
    ),
    EvidenceField(
        "LOW_SO_FAR_C", "Opening", Timing.CHECKPOINT_DYNAMIC, Provenance.NOT_APPLICABLE,
        Classification.EVIDENCE_ONLY,
        "min(low) over session T's M5 candles with ts_open < C (same boundary as HIGH_SO_FAR_C)", None,
        ("no M5 candles with ts_open < C",),
    ),
    EvidenceField(
        "RANGE_SO_FAR_C", "Opening", Timing.CHECKPOINT_DYNAMIC, Provenance.NOT_APPLICABLE,
        Classification.CANDIDATE_FEATURE,
        "(HIGH_SO_FAR_C - LOW_SO_FAR_C) / session_open[T]", None,
        ("HIGH_SO_FAR_C or LOW_SO_FAR_C is UNKNOWN",),
    ),
    EvidenceField(
        "DIST_FROM_HIGH_SO_FAR_C", "Opening", Timing.CHECKPOINT_DYNAMIC, Provenance.NOT_APPLICABLE,
        Classification.CANDIDATE_FEATURE,
        "price_at_checkpoint(C) / HIGH_SO_FAR_C - 1", None,
        ("HIGH_SO_FAR_C is UNKNOWN", "no candle at exactly C"),
    ),
    EvidenceField(
        "VWAP_THROUGH_C", "Opening", Timing.CHECKPOINT_DYNAMIC, Provenance.NOT_APPLICABLE,
        Classification.EVIDENCE_ONLY,
        "canonical session VWAP, computed over session T's M5 candles with ts_open < C only "
        "(reuses athena.indicators.calculations.vwap unchanged, pre-filtering its candle input)", None,
        ("no M5 candles with ts_open < C", "cumulative volume through C is zero"),
    ),
    EvidenceField(
        "VWAP_REL_C", "Opening", Timing.CHECKPOINT_DYNAMIC, Provenance.NOT_APPLICABLE,
        Classification.CANDIDATE_FEATURE,
        "price_at_checkpoint(C) / VWAP_THROUGH_C - 1", None,
        ("VWAP_THROUGH_C is UNKNOWN", "no candle at exactly C"),
    ),
)

ALL_FIELDS = SESSION_INVARIANT_FIELDS + CHECKPOINT_DYNAMIC_FIELDS

SESSION_INVARIANT_FIELD_COUNT = len(SESSION_INVARIANT_FIELDS)  # 15 (13 PRIOR_HISTORY + 2 SESSION_OPEN_CONTEXT)
CHECKPOINT_DYNAMIC_FIELD_COUNT = len(CHECKPOINT_DYNAMIC_FIELDS)  # 13
TOTAL_FIELD_COUNT = len(ALL_FIELDS)  # 28
