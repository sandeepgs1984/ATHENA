"""Coverage planning (SU-5, ADR-011).

The change that makes scanner-specific universes actually affordable: membership
of a discovery universe stops implying permanent ingestion for every subsystem.

```
resolve_universe(name) → symbols
   → coverage requirement (timeframe, minimum bars)
   → planner: which symbols fall short
   → bounded backfill of only those
```

Before this, "in the scanner's universe" and "has candles in the ledger" were
the same statement, so widening one meant widening the other for everybody.

## Planning is separate from execution, deliberately

`plan_coverage` reads and reports; it fetches nothing. `execute_backfill` is the
only thing that talks to a provider, and it is **bounded by an explicit limit**
rather than defaulting to "everything". A 2,700-symbol universe at Kite's
~3 requests/second is roughly fifteen minutes of continuous fetching — not
something any function should start because a caller asked what was missing.

## One failing symbol never stops the batch

Per-symbol failure isolation, with the failure recorded and returned. A delisted
or renamed ticker must cost exactly one symbol, never the run — the same
discipline the DarvaX scan and the group builders already follow.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta

from athena.domain.enums import Timeframe

logger = logging.getLogger(__name__)

#: Kite's historical rate limit, used only to *estimate* how long a backfill
#: would take. The transport enforces the real thing; this is for telling the
#: owner what they are about to start.
DEFAULT_REQUEST_INTERVAL_SECONDS = 0.334


@dataclass(frozen=True, slots=True)
class CoverageRequirement:
    """What a scanner needs before it can run: bars of a given timeframe."""

    timeframe: Timeframe
    minimum_bars: int
    reason: str = ""
    """Why this many — e.g. the methodology setting it comes from. Recorded so a
    requirement is traceable to something rather than looking arbitrary."""

    def __post_init__(self) -> None:
        if self.minimum_bars < 1:
            raise ValueError(f"minimum_bars must be >= 1, got {self.minimum_bars}")


@dataclass(frozen=True, slots=True)
class CoverageGap:
    """One instrument short of the requirement."""

    instrument_id: str
    have: int
    need: int

    @property
    def shortfall(self) -> int:
        return self.need - self.have


@dataclass(frozen=True, slots=True)
class CoveragePlan:
    """What a universe already has, what it lacks, and what filling it costs."""

    universe: str
    requirement: CoverageRequirement
    satisfied: tuple[str, ...]
    gaps: tuple[CoverageGap, ...]

    @property
    def is_satisfied(self) -> bool:
        return not self.gaps

    @property
    def estimated_requests(self) -> int:
        """One historical request per gap: a single daily call covers a year,
        measured during the SU-1 investigation."""
        return len(self.gaps)

    def estimated_seconds(
        self, interval: float = DEFAULT_REQUEST_INTERVAL_SECONDS
    ) -> float:
        return self.estimated_requests * interval

    def summary(self) -> str:
        return (
            f"{self.universe}: {len(self.satisfied)} covered, {len(self.gaps)} short "
            f"of {self.requirement.minimum_bars} {self.requirement.timeframe.value} "
            f"bars (~{self.estimated_requests} requests, "
            f"~{self.estimated_seconds() / 60:.1f} min)"
        )


class CoverageReader:
    """Structural type: the one read planning needs."""

    def candle_coverage(
        self, timeframe: Timeframe, instrument_ids: Sequence[str]
    ) -> dict[str, int]: ...


def plan_coverage(
    universe: str,
    symbols: Sequence[str],
    requirement: CoverageRequirement,
    reader: CoverageReader,
) -> CoveragePlan:
    """Report which symbols fall short. **Fetches nothing.**"""
    counts = reader.candle_coverage(requirement.timeframe, symbols)
    satisfied: list[str] = []
    gaps: list[CoverageGap] = []
    for instrument_id in sorted(symbols):
        have = counts.get(instrument_id, 0)
        if have >= requirement.minimum_bars:
            satisfied.append(instrument_id)
        else:
            gaps.append(
                CoverageGap(
                    instrument_id=instrument_id,
                    have=have,
                    need=requirement.minimum_bars,
                )
            )
    return CoveragePlan(
        universe=universe,
        requirement=requirement,
        satisfied=tuple(satisfied),
        gaps=tuple(gaps),
    )


@dataclass(frozen=True, slots=True)
class BackfillOutcome:
    """What a bounded backfill actually did."""

    attempted: tuple[str, ...]
    filled: tuple[str, ...]
    failed: tuple[tuple[str, str], ...]
    """``(instrument_id, reason)`` — surfaced, never swallowed."""
    remaining: int
    """Gaps left unattempted because the limit was reached. Reported so a
    partial run is never mistaken for a complete one."""


def execute_backfill(
    plan: CoveragePlan,
    *,
    fetch: Callable[[str, date, date], int],
    limit: int,
    end: date,
    lookback_days: int,
) -> BackfillOutcome:
    """Fill the plan's gaps, up to ``limit`` symbols, isolating failures.

    Args:
        fetch: ``(instrument_id, start, end) -> bars_written``. Injected so this
            function has no provider or repository dependency of its own, which
            keeps it testable without a network and keeps provider choice where
            ADR-002 put it.
        limit: **required**, with no default. A backfill that silently defaults
            to "everything" is how a fifteen-minute network operation starts by
            accident.
    """
    if limit < 1:
        raise ValueError(f"limit must be >= 1, got {limit}")

    targets = [gap.instrument_id for gap in plan.gaps[:limit]]
    start = end - timedelta(days=lookback_days - 1)
    filled: list[str] = []
    failed: list[tuple[str, str]] = []

    for instrument_id in targets:
        try:
            written = fetch(instrument_id, start, end)
        except Exception as exc:  # one symbol must never cost the run
            failed.append((instrument_id, f"{type(exc).__name__}: {exc}"))
            logger.warning(
                "coverage backfill skipped %s: %s — continuing with the rest",
                instrument_id, exc,
            )
            continue
        if written:
            filled.append(instrument_id)
        else:
            # No error, but nothing came back: the symbol resolves yet has no
            # history in the window. Recorded rather than counted as success.
            failed.append((instrument_id, "provider returned no candles"))

    return BackfillOutcome(
        attempted=tuple(targets),
        filled=tuple(filled),
        failed=tuple(failed),
        remaining=max(0, len(plan.gaps) - len(targets)),
    )
