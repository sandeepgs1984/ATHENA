"""EM-5's scanner state machine -- the exact frozen contract from
`docs/design/EM-5-LIVE-SCANNER-CONTRACT.md` Section 3 (Owner-approved
2026-08-28, rank cutoffs 20/10/5, FADING recovery completed).

Purely rank/eligibility-driven -- no FINAL_TEST-derived probability
threshold anywhere (Blocker 1). The same rule is applied fresh at every
checkpoint regardless of current state, so `FADING` recovery is not a
special case: a candidate whose rank recovers into a tier it already
proved this session (`ever_reached`) or held at the immediately prior
checkpoint re-enters that tier through the identical rule a fresh
candidate would use to earn it the first time.

A state is a research observation only -- this module has no
connection to, and cannot reach, ATHENA `Decision`/confidence/risk/
portfolio/order/execution (enforced by `test_em5_isolation.py`).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ScannerState(str, Enum):
    INACTIVE = "INACTIVE"
    WATCH = "WATCH"
    DEVELOPING = "DEVELOPING"
    CONFIRMED = "CONFIRMED"
    HIGH_CONVICTION = "HIGH_CONVICTION"
    FADING = "FADING"
    INVALIDATED = "INVALIDATED"
    TARGET_REACHED = "TARGET_REACHED"


#: Terminal states -- no further transitions for that symbol/target/session.
TERMINAL_STATES = frozenset({ScannerState.INVALIDATED, ScannerState.TARGET_REACHED})

#: Ordinal tier level for "ever_reached"/progression comparisons.
#: WATCH and DEVELOPING share a tier (both are the rank<=20 band,
#: differentiated only by sustained/improving momentum, not by a
#: different rank cutoff) -- FADING/INACTIVE carry no achieved tier.
_TIER_LEVEL: dict[ScannerState, int] = {
    ScannerState.INACTIVE: 0, ScannerState.FADING: 0,
    ScannerState.WATCH: 1, ScannerState.DEVELOPING: 1,
    ScannerState.CONFIRMED: 2, ScannerState.HIGH_CONVICTION: 3,
}


@dataclass(frozen=True, slots=True)
class RankCutoffs:
    """Ordinal shortlist-size cutoffs -- configuration, not a statistic
    measured from any partition (Owner-approved default: 20/10/5)."""

    watch_rank: int = 20
    confirmed_rank: int = 10
    high_conviction_rank: int = 5


DEFAULT_RANK_CUTOFFS = RankCutoffs()


@dataclass(frozen=True, slots=True)
class StateTransitionResult:
    from_state: ScannerState
    to_state: ScannerState
    reason: str


def _rank_tier(rank: int | None, cutoffs: RankCutoffs) -> ScannerState | None:
    """None means BELOW_SHORTLIST (or unranked) -- rank ties to no
    specific state on its own, only via `ever_reached`/prior_state below."""

    if rank is None:
        return None
    if rank <= cutoffs.high_conviction_rank:
        return ScannerState.HIGH_CONVICTION
    if rank <= cutoffs.confirmed_rank:
        return ScannerState.CONFIRMED
    if rank <= cutoffs.watch_rank:
        return ScannerState.WATCH
    return None


def determine_next_state(
    *,
    rank: int | None,
    hard_ineligible: bool,
    already_occurred: bool,
    prior_state: ScannerState,
    prior_rank: int | None,
    ever_reached: ScannerState,
    hard_ineligible_reason: str | None = None,
    rank_cutoffs: RankCutoffs = DEFAULT_RANK_CUTOFFS,
) -> StateTransitionResult:
    """Pure, deterministic, evidence-only. `ever_reached` is the highest
    tier this candidate has held at any earlier checkpoint this session
    (a plain fact read back from the persisted transition log, not a
    new hidden variable)."""

    if prior_state in TERMINAL_STATES:
        return StateTransitionResult(prior_state, prior_state, "terminal state, no further transitions")

    if already_occurred:
        return StateTransitionResult(prior_state, ScannerState.TARGET_REACHED, "ALREADY_OCCURRED evidence fired")

    if hard_ineligible:
        reason = hard_ineligible_reason or "hard eligibility/feasibility failure"
        return StateTransitionResult(prior_state, ScannerState.INVALIDATED, reason)

    tier = _rank_tier(rank, rank_cutoffs)
    ever_level = _TIER_LEVEL[ever_reached]

    if tier == ScannerState.HIGH_CONVICTION:
        if ever_level >= _TIER_LEVEL[ScannerState.CONFIRMED] or prior_state == ScannerState.CONFIRMED:
            reason = f"rank {rank} <= {rank_cutoffs.high_conviction_rank}, sustained from CONFIRMED"
            return StateTransitionResult(prior_state, ScannerState.HIGH_CONVICTION, reason)
        reason = (
            f"rank {rank} <= {rank_cutoffs.high_conviction_rank} but not yet "
            "sustained -- capped at CONFIRMED"
        )
        return StateTransitionResult(prior_state, ScannerState.CONFIRMED, reason)

    if tier == ScannerState.CONFIRMED:
        if ever_level >= _TIER_LEVEL[ScannerState.WATCH] or prior_state in (
            ScannerState.WATCH,
            ScannerState.DEVELOPING,
        ):
            reason = f"rank {rank} <= {rank_cutoffs.confirmed_rank}, sustained from WATCH/DEVELOPING"
            return StateTransitionResult(prior_state, ScannerState.CONFIRMED, reason)
        reason = f"rank {rank} <= {rank_cutoffs.confirmed_rank} but not yet sustained -- capped at WATCH"
        return StateTransitionResult(prior_state, ScannerState.WATCH, reason)

    if tier == ScannerState.WATCH:
        improved = prior_rank is not None and rank is not None and rank < prior_rank
        # prior_state == FADING implies ever_level >= WATCH already (that is
        # the only way to reach FADING, see the BELOW_SHORTLIST branch below)
        # -- recovering from FADING counts as sustained, not a fresh entry.
        sustained = prior_state in (ScannerState.WATCH, ScannerState.DEVELOPING, ScannerState.FADING)
        if improved or sustained:
            reason = f"rank {rank} <= {rank_cutoffs.watch_rank}, sustained or improved"
            return StateTransitionResult(prior_state, ScannerState.DEVELOPING, reason)
        reason = f"rank {rank} <= {rank_cutoffs.watch_rank}, first checkpoint in band"
        return StateTransitionResult(prior_state, ScannerState.WATCH, reason)

    # BELOW_SHORTLIST (tier is None)
    if ever_level >= _TIER_LEVEL[ScannerState.WATCH]:
        reason = f"rank {rank} outside all bands, was previously WATCH+ this session"
        return StateTransitionResult(prior_state, ScannerState.FADING, reason)
    return StateTransitionResult(prior_state, ScannerState.INACTIVE, "never qualified, still does not")
