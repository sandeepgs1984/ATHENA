"""What the owner holds in the DarvaX lane (DX-7b, ADR-010).

**Why DarvaX keeps its own list.** ATHENA has an ``owner_positions`` table, and
reading it would have been one method on the port. The owner chose a separate
list instead (advisor design §4, decision 1a), keeping the two lanes genuinely
independent — which is ADR-010's own principle. The cost is accepted and stated
rather than hidden: **nothing reconciles the two records.** A position closed in
ATHENA stays open here until it is closed here too, and DarvaX will keep saying
HOLD about it.

A position exists here for exactly one purpose: three of the five advisor
actions are meaningless without it. ``HOLD`` and ``EXIT`` are claims about a
position, and ``EXIT_IF_HELD`` is the hedge DarvaX had to use while it could not
tell. Nothing here sizes a trade, allocates capital, or places an order.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from athena.darvax.signals.models import StopBasis


@dataclass(frozen=True, slots=True)
class DarvaxPosition:
    """One open or closed holding in the DarvaX lane.

    Closing sets ``closed_at`` rather than deleting the row: a closed position
    is the record of a completed round trip, and deleting it would destroy the
    only history DarvaX has of its own advice being acted on.
    """

    position_id: str
    instrument_id: str
    quantity: int
    """Shares held. An integer because NSE equities trade in whole shares."""
    entry_price: Decimal
    entry_date: date
    opened_at: datetime
    stop_price: Decimal | None = None
    """The level below which the methodology says to exit. Computed from the
    stop policy at the moment the position was opened and **frozen there**:
    if the policy is later changed from 10% to 1%, an existing position keeps
    the stop it was actually protected by. The same reasoning as persisting
    ``methodology_digest`` on a signal."""
    stop_basis: StopBasis | None = None
    """Which documented rule produced ``stop_price`` — so a stop is never a
    bare number whose origin nobody can state (ADR-005)."""
    methodology_digest: str = ""
    """The methodology settings in force when the stop was computed."""
    closed_at: datetime | None = None
    note: str = ""

    @property
    def is_open(self) -> bool:
        return self.closed_at is None

    def unrealised_pct(self, price: Decimal) -> Decimal | None:
        """Return at ``price`` against entry, as a percentage.

        A **display** quantity, computed on demand from two stored numbers
        rather than persisted: unlike an action or an explanation, it has no
        rule behind it to record and it changes with every tick, so freezing it
        would create a stale field that looks authoritative.
        """
        if self.entry_price <= 0:
            return None
        return ((price - self.entry_price) / self.entry_price * Decimal(100)).quantize(
            Decimal("0.01")
        )
