"""EM-4C evaluation scaffolding: deterministic ranking, tie-breaking,
Precision@K, Lift@K, base-rate comparison.

Owner/Chief Architect decision, 2026-08-27 (evaluation-scaffolding scope):
build the reusable pure-Python evaluation infrastructure EM-4C will need
*before* the logistic baseline exists, so it can be tested against
fixtures/synthetic data only. This module computes nothing from real
VALIDATION outcomes -- callers supply the (already-scored) observations,
real or synthetic, and this module is blind to which.

Ranking is a cross-section concept: one (session_date, checkpoint,
family, threshold) group of scored observations, ranked against each
other -- never pooled across cross-sections (per the EM-4 Modeling
Contract's session-date x checkpoint evaluation requirement).

Tie-break rule (frozen here, v1): primary sort by score descending;
ties broken by instrument_id ascending. Arbitrary but deterministic and
documented -- matches this workstream's "no ties split silently"
convention (see conditional_analysis.assign_bin). Ties are expected to
be rare with continuous scores; if EM-4C finds this rule materially
affects real results, that becomes an Owner decision at that point.

Pure: no I/O, no randomness.
"""

from __future__ import annotations

from dataclasses import dataclass

EM4C_RANKING_CONTRACT_VERSION = "em4c-ranking-v1"


@dataclass(frozen=True, slots=True)
class ScoredObservation:
    instrument_id: str
    score: float | None  # None == UNKNOWN, excluded from ranking
    label: bool


@dataclass(frozen=True, slots=True)
class PrecisionAtKResult:
    k: int
    k_effective: int  # min(k, eligible_n) -- the population actually ranked over
    eligible_n: int
    positive_in_top_k: int
    precision: float | None  # None iff eligible_n == 0
    population_below_k: bool
    unknown_reason: str | None


@dataclass(frozen=True, slots=True)
class LiftAtKResult:
    k: int
    precision_at_k: float | None
    base_rate: float | None
    lift: float | None  # precision_at_k / base_rate; None if either input is None or base_rate == 0
    unknown_reason: str | None


def rank_observations(observations: tuple[ScoredObservation, ...]) -> tuple[ScoredObservation, ...]:
    """Known-score observations only, ranked score-descending with the
    frozen instrument_id-ascending tie-break. Deterministic: identical
    input always produces identical output order (replay-safe)."""

    known = [o for o in observations if o.score is not None]
    return tuple(sorted(known, key=lambda o: (-o.score, o.instrument_id)))


def base_rate(observations: tuple[ScoredObservation, ...]) -> float | None:
    """Unconditional positive rate over ALL observations in the
    cross-section (including UNKNOWN-scored ones -- base rate is a
    property of the population, not of what the model could score)."""

    if not observations:
        return None
    return sum(1 for o in observations if o.label) / len(observations)


def precision_at_k(observations: tuple[ScoredObservation, ...], k: int) -> PrecisionAtKResult:
    if k <= 0:
        raise ValueError(f"k must be positive, got {k}")

    ranked = rank_observations(observations)
    eligible_n = len(ranked)
    if eligible_n == 0:
        return PrecisionAtKResult(
            k=k, k_effective=0, eligible_n=0, positive_in_top_k=0, precision=None,
            population_below_k=True, unknown_reason="no known-score observations in this cross-section",
        )

    k_effective = min(k, eligible_n)
    top = ranked[:k_effective]
    positives = sum(1 for o in top if o.label)
    return PrecisionAtKResult(
        k=k, k_effective=k_effective, eligible_n=eligible_n, positive_in_top_k=positives,
        precision=positives / k_effective, population_below_k=eligible_n < k, unknown_reason=None,
    )


def lift_at_k(observations: tuple[ScoredObservation, ...], k: int) -> LiftAtKResult:
    precision_result = precision_at_k(observations, k)
    rate = base_rate(observations)

    if precision_result.precision is None:
        return LiftAtKResult(
            k=k, precision_at_k=None, base_rate=rate, lift=None,
            unknown_reason=precision_result.unknown_reason,
        )
    if rate is None or rate == 0:
        return LiftAtKResult(
            k=k, precision_at_k=precision_result.precision, base_rate=rate, lift=None,
            unknown_reason="base_rate is zero or undefined -- lift is undefined",
        )
    return LiftAtKResult(
        k=k, precision_at_k=precision_result.precision, base_rate=rate,
        lift=precision_result.precision / rate, unknown_reason=None,
    )
