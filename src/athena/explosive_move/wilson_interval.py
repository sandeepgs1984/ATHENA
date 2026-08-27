"""Wilson score confidence interval for a binomial proportion -- EM-1c's
uncertainty measure for base rates. Preferred over the normal
(Wald) approximation because it stays well-behaved at small n and
extreme (rare-event) proportions, both of which are the norm here
(TOUCH_20 base rates are often well under 0.1%).

Pure, no I/O, no randomness.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

#: 95% confidence, the conventional default this report uses throughout.
DEFAULT_Z = 1.959963984540054


@dataclass(frozen=True, slots=True)
class WilsonInterval:
    point_estimate: float
    lower: float
    upper: float

    @property
    def half_width(self) -> float:
        return (self.upper - self.lower) / 2


#: EM-1c minimum-support policy (owner-approved scope: "freeze the
#: minimum-support policy that prevents very small cohorts from being
#: promoted regardless of apparent lift"). Derived from the real TRAIN
#: distribution, not picked blindly: at n>=1000 and k>=10, family/
#: threshold/year/regime breakdowns pass almost universally (their real
#: populations are large), while sector breakdowns -- the genuinely
#: small-cohort case -- correctly fail ~25% of the time (95/378 real
#: sector x family x threshold cells), concentrated exactly where
#: intuition says they should be: small sectors at rare thresholds.
#: A subgroup failing either bound may still be reported descriptively,
#: but must never be used to support a promotion/selection decision in
#: EM-2/EM-3 regardless of how favorable its apparent rate looks.
MIN_ELIGIBLE_N = 1000
MIN_POSITIVE_K = 10


def meets_minimum_support(*, eligible_n: int, positive_k: int) -> bool:
    return eligible_n >= MIN_ELIGIBLE_N and positive_k >= MIN_POSITIVE_K


def wilson_interval(successes: int, n: int, *, z: float = DEFAULT_Z) -> WilsonInterval:
    if n < 0 or successes < 0 or successes > n:
        raise ValueError(f"invalid successes={successes} for n={n}")
    if n == 0:
        return WilsonInterval(point_estimate=0.0, lower=0.0, upper=1.0)

    p_hat = successes / n
    z2 = z * z
    denom = 1 + z2 / n
    center = (p_hat + z2 / (2 * n)) / denom
    half = (z / denom) * math.sqrt(p_hat * (1 - p_hat) / n + z2 / (4 * n * n))
    return WilsonInterval(
        point_estimate=p_hat, lower=max(0.0, center - half), upper=min(1.0, center + half),
    )
