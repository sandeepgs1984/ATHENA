"""EM-4 frozen methodological configuration -- Owner/Chief Architect
decision, 2026-08-27. These four items were required to be frozen
*before* fitting anything (EM-4 Modeling Contract, item 17): exact
chronological internal TRAIN CV folds, the single primary regularization
-selection metric, the Platt minimum-support policy, and the exact
MFE/MAE/time-to-target formulas/horizons.

Pure metadata + pure computation. No I/O, no model fitting.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

EM4_CONFIG_VERSION = "em4-config-v1"

# --------------------------------------------------------------------------- #
# 1. Chronological, session-grouped, expanding-window TRAIN-internal CV folds.
# Never random/shuffled; a whole session always stays in one fold-role.
# Base window = first 50% of TRAIN (220 of 440 sessions); the remaining 220
# sessions split into 4 expanding-eval blocks of 55 sessions each. Frozen as
# exact real TRAIN session dates, not fractions, so the fold assignment is
# reproducible independent of any future re-count of TRAIN's session list.
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class TemporalFold:
    fold_id: int
    fit_through: date  # inclusive -- fit uses all TRAIN sessions with date <= this
    eval_start: date  # inclusive
    eval_end: date  # inclusive


TEMPORAL_CV_FOLDS: tuple[TemporalFold, ...] = (
    TemporalFold(1, date(2024, 7, 9), date(2024, 7, 10), date(2024, 9, 26)),
    TemporalFold(2, date(2024, 9, 26), date(2024, 9, 27), date(2024, 12, 18)),
    TemporalFold(3, date(2024, 12, 18), date(2024, 12, 19), date(2025, 3, 6)),
    TemporalFold(4, date(2025, 3, 6), date(2025, 3, 7), date(2025, 5, 30)),
)


def fold_for_session(session_date: date) -> int | None:
    """Which fold's EVAL block a TRAIN session belongs to, or None if it
    falls in the base (always-fit, never-eval) window before fold 1."""

    for fold in TEMPORAL_CV_FOLDS:
        if fold.eval_start <= session_date <= fold.eval_end:
            return fold.fold_id
    return None


# --------------------------------------------------------------------------- #
# 2. Single primary regularization-selection metric: PR-AUC, averaged across
# the 4 folds' held-out blocks. Chosen over ROC-AUC/accuracy (rare-event
# population; PR-AUC is the standard rare-event-appropriate scalar) and over
# Precision@K/Lift@K (those remain the PRIMARY real-world VALIDATION metrics
# in EM-4C, but require picking a K -- an extra arbitrary choice unsuitable
# for the narrower, purely internal job of picking one L2 strength).
# Applied identically across all 18 (family, threshold) models -- never
# swapped per model.
# --------------------------------------------------------------------------- #

CV_SELECTION_METRIC = "PR-AUC (average precision), averaged across the 4 temporal folds"

L2_REGULARIZATION_GRID: tuple[float, ...] = (0.01, 0.1, 1.0, 10.0)


# --------------------------------------------------------------------------- #
# 3. Platt minimum-support policy: reuses EM-1c's already-frozen minimum-
# support policy exactly (n>=1000 eligible, k>=10 positive) -- no new number
# invented. Checkpoint-specific first; falls back to pooled family x
# threshold; otherwise UNCALIBRATED / INSUFFICIENT_SUPPORT. Isotonic is
# never used automatically -- only ever proposed later if CALIBRATION
# support clears a materially higher bar (k>=50, per the owner's guidance),
# and only as an explicit separate decision at EM-4D.
# --------------------------------------------------------------------------- #

PLATT_MIN_ELIGIBLE_N = 1000
PLATT_MIN_POSITIVE_K = 10
ISOTONIC_CONSIDERATION_MIN_POSITIVE_K = 50  # not auto-applied; a candidacy bar only


def meets_platt_minimum(*, eligible_n: int, positive_k: int) -> bool:
    return eligible_n >= PLATT_MIN_ELIGIBLE_N and positive_k >= PLATT_MIN_POSITIVE_K


# --------------------------------------------------------------------------- #
# 4. MFE / MAE / time-to-target: exact formulas, derived directly from
# already-frozen EM-1a/EM-1b conventions -- reference_price
# (config/explosive_move.json's event_contract.reference_prices) and the
# same forward-candle boundary (ts_open >= checkpoint_instant) already
# tested in EM-1b's event_labels.py. No new semantics invented.
#
# MFE (Max Favorable Excursion, %) = max(high over forward candles) / reference_price - 1, x100
# MAE (Max Adverse  Excursion, %) = min(low  over forward candles) / reference_price - 1, x100
#   forward candles = session T's M5 candles with ts_open >= checkpoint_instant
#   (the same_regular_session horizon, frozen in config/explosive_move.json's
#   target_horizon -- MFE/MAE never look beyond session T's own close).
#   UNKNOWN if no forward candles exist (checkpoint at/after the last candle).
#
# time_to_target (minutes) = (first forward candle whose high >= threshold_price).ts_open
#                             - checkpoint_instant, in minutes
#   Computed only for TOUCH/OPEN_TO_HIGH (families with a genuine touch
#   mechanism) and only for POSITIVE-labelled cases. NOT_APPLICABLE for
#   CLOSE (whose "event" is the session close itself, not a specific
#   forward candle -- matching event_labels.py's own documented design:
#   CLOSE has no ALREADY_OCCURRED/touch concept).
# --------------------------------------------------------------------------- #

MFE_MAE_HORIZON = "same_regular_session (forward candles only: ts_open >= checkpoint_instant)"
TIME_TO_TARGET_APPLICABLE_FAMILIES = ("TOUCH", "OPEN_TO_HIGH")
