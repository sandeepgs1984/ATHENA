"""Capital Allocation Engine implementation (P5.2).

Determines capital allocation policy only — evaluates available portfolio capital and allocates to approved investment opportunities.
Performs NO market analysis, NO position sizing (share quantities), and NO order execution.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from athena.allocation.models import (
    AllocationHistory,
    AllocationPlan,
    AllocationReferences,
    AllocationSummary,
    CapitalAllocation,
)
from athena.config.models import AllocationConfig, AllocationModel
from athena.domain.decision import Decision
from athena.domain.enums import DecisionType
from athena.errors import AllocationError
from athena.portfolio.models import PortfolioSnapshot

_TWO_PLACES = Decimal("0.01")


def _quantize(val: Decimal) -> Decimal:
    return val.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


class CapitalAllocationEngine:
    """Deterministic, policy-driven Capital Allocation Engine."""

    def __init__(self, config: AllocationConfig | None = None) -> None:
        self._config = config or AllocationConfig()
        self._counter = 0
        self._history = AllocationHistory()

    @property
    def history(self) -> AllocationHistory:
        """Get accumulated allocation history."""
        return self._history

    def allocate(
        self,
        portfolio_snapshot: PortfolioSnapshot,
        opportunities: Sequence[Decision],
        *,
        as_of: datetime,
        model: AllocationModel | None = None,
        strategy: str | None = None,
        watchlist: str | None = None,
        schedule_execution_id: str | None = None,
    ) -> AllocationPlan:
        """Allocate capital to candidate investment opportunities."""
        if as_of.tzinfo is None:
            raise ValueError("allocate as_of datetime must be timezone-aware")

        alloc_model = model or self._config.default_model
        total_cash = portfolio_snapshot.portfolio.cash.total_cash
        available_cash = portfolio_snapshot.portfolio.cash.available_cash

        # Calculate reserve floor
        min_reserve_floor = _quantize(
            (self._config.min_cash_reserve_pct / Decimal("100")) * total_cash
        )
        allocatable_pool = max(Decimal("0.00"), available_cash - min_reserve_floor)

        # Filter valid candidate opportunities (TRADE / INCREASE_POSITION)
        candidates: list[Decision] = []
        non_candidates: list[Decision] = []

        for opp in opportunities:
            if opp.decision_type in (DecisionType.TRADE, DecisionType.INCREASE_POSITION):
                candidates.append(opp)
            else:
                non_candidates.append(opp)

        # Sort candidate opportunities deterministically by instrument_id
        candidates.sort(key=lambda d: d.instrument_id or "")
        non_candidates.sort(key=lambda d: d.instrument_id or "")

        active_candidates = candidates[: self._config.max_opportunities]
        excess_candidates = candidates[self._config.max_opportunities :]

        # Determine target allocation per active candidate
        num_active = len(active_candidates)
        if alloc_model == AllocationModel.FIXED_AMOUNT:
            target_alloc = _quantize(self._config.fixed_amount)
        elif alloc_model == AllocationModel.FIXED_PERCENTAGE:
            target_alloc = _quantize(
                (self._config.fixed_percentage / Decimal("100")) * total_cash
            )
        elif alloc_model == AllocationModel.EQUAL_WEIGHT:
            if num_active > 0:
                target_alloc = _quantize(allocatable_pool / Decimal(num_active))
            else:
                target_alloc = Decimal("0.00")
        else:
            raise AllocationError(f"Unsupported AllocationModel: {alloc_model}")

        allocations: list[CapitalAllocation] = []
        allocated_count = 0
        rejected_count = 0
        total_allocated = Decimal("0.00")

        # Process active candidates
        for opp in active_candidates:
            inst_id = opp.instrument_id or "UNKNOWN"
            refs = AllocationReferences(
                portfolio_snapshot_id=portfolio_snapshot.snapshot_id,
                decision_id=opp.decision_id,
                strategy=strategy,
                watchlist=watchlist,
                schedule_execution_id=schedule_execution_id,
            )

            req_amount = target_alloc

            if req_amount <= Decimal("0.00"):
                status = "REJECTED_ZERO_TARGET"
                alloc_amt = Decimal("0.00")
                expl = "Target allocation calculated to zero"
                rejected_count += 1
            elif allocatable_pool >= req_amount:
                status = "ALLOCATED"
                alloc_amt = req_amount
                allocatable_pool -= req_amount
                expl = f"Fully allocated target {req_amount} via {alloc_model.value}"
                allocated_count += 1
                total_allocated += alloc_amt
            elif allocatable_pool > Decimal("0.00"):
                status = "PARTIAL"
                alloc_amt = allocatable_pool
                expl = f"Partially allocated remaining pool {allocatable_pool} (target {req_amount})"
                allocatable_pool = Decimal("0.00")
                allocated_count += 1
                total_allocated += alloc_amt
            else:
                status = "REJECTED_INSUFFICIENT_CASH"
                alloc_amt = Decimal("0.00")
                expl = f"Rejected: cash pool exhausted (reserve floor {min_reserve_floor})"
                rejected_count += 1

            alloc_id = f"alloc-{self._next_counter():04d}"
            allocations.append(
                CapitalAllocation(
                    allocation_id=alloc_id,
                    instrument_id=inst_id,
                    allocated_amount=alloc_amt,
                    requested_amount=req_amount,
                    model_used=alloc_model,
                    status=status,
                    explanation=expl,
                    as_of=as_of,
                    references=refs,
                )
            )

        # Process excess candidates (beyond max_opportunities)
        for opp in excess_candidates:
            inst_id = opp.instrument_id or "UNKNOWN"
            refs = AllocationReferences(
                portfolio_snapshot_id=portfolio_snapshot.snapshot_id,
                decision_id=opp.decision_id,
                strategy=strategy,
                watchlist=watchlist,
                schedule_execution_id=schedule_execution_id,
            )

            alloc_id = f"alloc-{self._next_counter():04d}"
            allocations.append(
                CapitalAllocation(
                    allocation_id=alloc_id,
                    instrument_id=inst_id,
                    allocated_amount=Decimal("0.00"),
                    requested_amount=target_alloc,
                    model_used=alloc_model,
                    status="REJECTED_MAX_OPPORTUNITIES",
                    explanation=f"Rejected: exceeds max_opportunities limit ({self._config.max_opportunities})",
                    as_of=as_of,
                    references=refs,
                )
            )
            rejected_count += 1

        # Process non-candidates (NO_TRADE, WATCH, etc.)
        for opp in non_candidates:
            inst_id = opp.instrument_id or "UNKNOWN"
            refs = AllocationReferences(
                portfolio_snapshot_id=portfolio_snapshot.snapshot_id,
                decision_id=opp.decision_id,
                strategy=strategy,
                watchlist=watchlist,
                schedule_execution_id=schedule_execution_id,
            )

            alloc_id = f"alloc-{self._next_counter():04d}"
            allocations.append(
                CapitalAllocation(
                    allocation_id=alloc_id,
                    instrument_id=inst_id,
                    allocated_amount=Decimal("0.00"),
                    requested_amount=Decimal("0.00"),
                    model_used=alloc_model,
                    status="REJECTED_NON_CANDIDATE",
                    explanation=f"Non-candidate decision type: {opp.decision_type.value}",
                    as_of=as_of,
                    references=refs,
                )
            )

        rem_cash = available_cash - total_allocated
        summary = AllocationSummary(
            as_of=as_of,
            total_candidates=len(opportunities),
            allocated_count=allocated_count,
            rejected_count=rejected_count,
            total_allocated_capital=total_allocated,
            remaining_available_cash=rem_cash,
            min_cash_reserve_floor=min_reserve_floor,
        )

        plan_id = f"plan-{self._next_counter():04d}"
        plan_refs = AllocationReferences(
            portfolio_snapshot_id=portfolio_snapshot.snapshot_id,
            strategy=strategy,
            watchlist=watchlist,
            schedule_execution_id=schedule_execution_id,
        )

        plan = AllocationPlan(
            plan_id=plan_id,
            as_of=as_of,
            portfolio_snapshot_id=portfolio_snapshot.snapshot_id,
            allocations=tuple(allocations),
            summary=summary,
            references=plan_refs,
        )

        if self._config.record_history:
            self._history = self._history.record(plan)

        return plan

    def allocate_amount(
        self,
        portfolio_snapshot: PortfolioSnapshot,
        instrument_id: str,
        amount: Decimal,
        *,
        as_of: datetime,
        model: AllocationModel | None = None,
        references: AllocationReferences | None = None,
    ) -> CapitalAllocation:
        """Explicitly allocate capital amount for a single opportunity."""
        if as_of.tzinfo is None:
            raise ValueError("allocate_amount as_of datetime must be timezone-aware")
        if amount <= Decimal("0.00"):
            raise AllocationError(f"Requested allocation amount must be > 0, got {amount}")

        alloc_model = model or self._config.default_model
        total_cash = portfolio_snapshot.portfolio.cash.total_cash
        available_cash = portfolio_snapshot.portfolio.cash.available_cash

        min_reserve_floor = _quantize(
            (self._config.min_cash_reserve_pct / Decimal("100")) * total_cash
        )
        allocatable_pool = max(Decimal("0.00"), available_cash - min_reserve_floor)

        refs = references or AllocationReferences(
            portfolio_snapshot_id=portfolio_snapshot.snapshot_id
        )

        if amount <= allocatable_pool:
            status = "ALLOCATED"
            alloc_amt = amount
            expl = f"Explicitly allocated {amount}"
        elif allocatable_pool > Decimal("0.00"):
            status = "PARTIAL"
            alloc_amt = allocatable_pool
            expl = f"Partially allocated remaining pool {allocatable_pool} (requested {amount})"
        else:
            status = "REJECTED_INSUFFICIENT_CASH"
            alloc_amt = Decimal("0.00")
            expl = f"Rejected: reserve floor {min_reserve_floor} reached"

        alloc_id = f"alloc-{self._next_counter():04d}"
        return CapitalAllocation(
            allocation_id=alloc_id,
            instrument_id=instrument_id,
            allocated_amount=alloc_amt,
            requested_amount=amount,
            model_used=alloc_model,
            status=status,
            explanation=expl,
            as_of=as_of,
            references=refs,
        )

    def _next_counter(self) -> int:
        self._counter += 1
        return self._counter
