"""EM-4A: the deterministic evidence score -- a plain, predeclared vote
over EM-3's own already-frozen EXPLORATORY_CANDIDATE register. Owner/
Chief Architect decision, 2026-08-27 (`em4-deterministic-v1`).

No lift magnitudes, no fitted weights: each admitted (feature, bin)
combination contributes exactly +1 (EM-3's absolute_difference > 0,
above the checkpoint baseline) or -1 (below baseline). Unsupported bins
(INSUFFICIENT_SUPPORT), UNKNOWN observations, and EVIDENCE_ONLY fields
never vote -- they are structurally absent from the compiled rule set,
not present-but-zero.

score = (positive_votes - negative_votes) / total_votes,  range [-1, +1]
score is UNKNOWN when total_votes == 0 (no admitted evidence available
for this observation at all).

Pure: no I/O. Rules are compiled once from EM-3's real register (loaded
by the caller) and reused across every observation scored.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from athena.explosive_move.conditional_analysis import assign_bin, bin_label

DETERMINISTIC_SCORE_CONTRACT_VERSION = "em4-deterministic-v1"

_CATEGORICAL_FIELDS = {"regime_trend", "regime_volatility", "regime_gap"}


@dataclass(frozen=True, slots=True)
class VoteRule:
    feature: str
    bin_label: str
    direction: int  # +1 or -1, never 0


@dataclass(frozen=True, slots=True)
class DeterministicScoreResult:
    score: float | None
    vote_count: int
    positive_vote_count: int
    negative_vote_count: int
    unknown_reason: str | None

    def __post_init__(self) -> None:
        if (self.score is None) != (self.vote_count == 0):
            raise ValueError("score is UNKNOWN iff vote_count == 0")
        if self.positive_vote_count + self.negative_vote_count != self.vote_count:
            raise ValueError("vote_count must equal positive + negative votes")


def compile_deterministic_rules(
    em3_register: list[dict],
) -> dict[tuple[str, int, str], tuple[VoteRule, ...]]:
    """Compile EM-3's real register into per-(family, threshold, checkpoint)
    rule sets. Only EXPLORATORY_CANDIDATE, non-UNKNOWN-bin entries with a
    genuinely nonzero absolute_difference become a rule."""

    grouped: dict[tuple[str, int, str], list[VoteRule]] = {}
    for entry in em3_register:
        if entry["classification"] != "EXPLORATORY_CANDIDATE":
            continue
        if entry["bin"] == "UNKNOWN":
            continue
        diff = entry["absolute_difference"]
        if diff == 0:
            continue
        direction = 1 if diff > 0 else -1
        key = (entry["family"], entry["threshold"], entry["checkpoint"])
        grouped.setdefault(key, []).append(
            VoteRule(feature=entry["feature"], bin_label=entry["bin"], direction=direction)
        )
    return {k: tuple(v) for k, v in grouped.items()}


def score_observation(
    *,
    rules: tuple[VoteRule, ...],
    evidence: dict[str, Decimal | str | None],
    bin_edges: dict[str, tuple[Decimal, ...]],
) -> DeterministicScoreResult:
    """`evidence` maps feature name -> its real value for this observation
    (None if UNKNOWN). `bin_edges` are EM-3's own frozen quintile edges
    (loaded from its manifest), keyed by feature name -- the identical
    edges EM-3 used, never re-derived here."""

    positive = negative = 0
    for rule in rules:
        value = evidence.get(rule.feature)
        if value is None:
            continue  # UNKNOWN never votes
        if rule.feature in _CATEGORICAL_FIELDS:
            observed_bin = value
        else:
            edges = bin_edges.get(rule.feature, ())
            observed_bin = bin_label(assign_bin(value, edges), edges)
        if observed_bin != rule.bin_label:
            continue
        if rule.direction > 0:
            positive += 1
        else:
            negative += 1

    total = positive + negative
    if total == 0:
        return DeterministicScoreResult(
            score=None, vote_count=0, positive_vote_count=0, negative_vote_count=0,
            unknown_reason="no admitted evidence available for this observation",
        )
    return DeterministicScoreResult(
        score=(positive - negative) / total, vote_count=total,
        positive_vote_count=positive, negative_vote_count=negative, unknown_reason=None,
    )
