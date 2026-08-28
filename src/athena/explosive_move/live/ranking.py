"""EM-5 ranking -- thin wrapper around the already-tested EM-4C ranking
scaffolding (`em4c_ranking.rank_observations`), producing a 1-indexed
rank position per instrument for one (session_date, checkpoint, family,
threshold) cross-section. No new ranking logic: reuses the frozen
tie-break rule (score descending, instrument_id-ascending ties)
unmodified.
"""

from __future__ import annotations

from athena.explosive_move.em4c_ranking import ScoredObservation, rank_observations


def rank_candidates(scores: dict[str, float]) -> dict[str, int]:
    """`scores` maps instrument_id -> calibrated probability for one
    cross-section. Returns instrument_id -> 1-indexed rank (1 = highest
    score). Instruments with no score must already be excluded from
    `scores` by the caller (ineligible candidates are never ranked)."""

    # `label` is required by ScoredObservation (an EM-4C evaluation type)
    # but never read by rank_observations -- there is no ground-truth
    # outcome at live-scan time, so it is a structurally-required,
    # semantically-unused placeholder here, not a fabricated label.
    observations = tuple(
        ScoredObservation(instrument_id=iid, score=score, label=False) for iid, score in scores.items()
    )
    ranked = rank_observations(observations)
    return {obs.instrument_id: position for position, obs in enumerate(ranked, start=1)}
