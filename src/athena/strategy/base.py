"""Strategy contract (M4.4).

A strategy is a named, versioned, deterministic *selection policy*. It receives
only completed :class:`InstrumentView`s (decision facts + watchlist memberships
already produced by ATHENA's core) and returns the subset it selects, each with
an explanation. A strategy must never invoke an analytical engine, read raw
market data, or compute an indicator.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from athena.strategy.models import InstrumentView, MatchProposal


class Strategy(ABC):
    """Abstract, deterministic selection policy over completed decision views."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable strategy identifier (unique within a framework)."""

    @property
    @abstractmethod
    def version(self) -> str:
        """Strategy version — bump when the selection rule changes."""

    @property
    @abstractmethod
    def description(self) -> str:
        """One-line description of the selection policy."""

    @abstractmethod
    def select(self, views: Sequence[InstrumentView]) -> tuple[MatchProposal, ...]:
        """Return the views this strategy selects, each with an explanation.

        Must be a pure, deterministic function of ``views`` (and the strategy's
        own immutable configuration) — no I/O, no clock reads, no randomness.
        """
