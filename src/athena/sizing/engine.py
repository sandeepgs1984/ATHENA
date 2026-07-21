"""Position Sizing Engine implementation (P5.3).

Converts approved capital allocations into executable share/unit quantities.
Performs NO market analysis, NO capital allocation policy decision, and NO order placement.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal, ROUND_DOWN, ROUND_UP

from athena.allocation.models import AllocationPlan
from athena.config.models import RoundingMode, SizingConfig, SizingModel
from athena.errors import SizingError
from athena.sizing.models import (
    PositionSize,
    PositionSizingHistory,
    PositionSizingPlan,
    PositionSizingSummary,
    SizingReferences,
)

_TWO_PLACES = Decimal("0.01")


def _quantize(val: Decimal) -> Decimal:
    return val.quantize(_TWO_PLACES, rounding=ROUND_DOWN)


class PositionSizingEngine:
    """Deterministic, policy-driven Position Sizing Engine."""

    def __init__(self, config: SizingConfig | None = None) -> None:
        self._config = config or SizingConfig()
        self._counter = 0
        self._history = PositionSizingHistory()

    @property
    def history(self) -> PositionSizingHistory:
        """Get accumulated sizing history."""
        return self._history

    def size_plan(
        self,
        allocation_plan: AllocationPlan,
        prices: Mapping[str, Decimal],
        *,
        as_of: datetime,
        model: SizingModel | None = None,
        rounding: RoundingMode | None = None,
    ) -> PositionSizingPlan:
        """Convert an AllocationPlan into a PositionSizingPlan based on instrument prices."""
        if as_of.tzinfo is None:
            raise ValueError("size_plan as_of datetime must be timezone-aware")

        sz_model = model or self._config.default_model
        rnd_mode = rounding or self._config.default_rounding

        sizes: list[PositionSize] = []
        sized_count = 0
        zero_count = 0
        tot_allocated = Decimal("0.00")
        tot_cost = Decimal("0.00")
        tot_qty = Decimal("0")

        # Process allocations sorted deterministically by instrument_id
        sorted_allocations = sorted(allocation_plan.allocations, key=lambda a: a.instrument_id)

        for alloc in sorted_allocations:
            inst_id = alloc.instrument_id
            price = prices.get(inst_id)
            refs = SizingReferences(
                allocation_plan_id=allocation_plan.plan_id,
                portfolio_snapshot_id=alloc.references.portfolio_snapshot_id,
                decision_id=alloc.references.decision_id,
                strategy=alloc.references.strategy,
                watchlist=alloc.references.watchlist,
                schedule_execution_id=alloc.references.schedule_execution_id,
            )

            tot_allocated += alloc.allocated_amount

            if price is None or price <= Decimal("0.00"):
                sz = PositionSize(
                    sizing_id=f"size-{self._next_counter():04d}",
                    instrument_id=inst_id,
                    allocated_amount=alloc.allocated_amount,
                    unit_price=price if price is not None else Decimal("0.00"),
                    quantity=Decimal("0"),
                    actual_cost=Decimal("0.00"),
                    sizing_model=sz_model,
                    rounding_mode=rnd_mode,
                    status="REJECTED_ZERO_PRICE",
                    explanation=f"Price unavailable or <= 0 for {inst_id}",
                    as_of=as_of,
                    references=refs,
                )
                zero_count += 1
            elif alloc.allocated_amount <= Decimal("0.00"):
                sz = PositionSize(
                    sizing_id=f"size-{self._next_counter():04d}",
                    instrument_id=inst_id,
                    allocated_amount=alloc.allocated_amount,
                    unit_price=price,
                    quantity=Decimal("0"),
                    actual_cost=Decimal("0.00"),
                    sizing_model=sz_model,
                    rounding_mode=rnd_mode,
                    status="ZERO_ALLOCATION",
                    explanation=f"Zero capital allocated to {inst_id} (allocation status: {alloc.status})",
                    as_of=as_of,
                    references=refs,
                )
                zero_count += 1
            else:
                raw_qty = alloc.allocated_amount / price
                qty = self._calculate_quantity(raw_qty, sz_model, rnd_mode)
                cost = _quantize(qty * price)

                status = "SIZED" if qty > Decimal("0") else "ZERO_ALLOCATION"
                expl = (
                    f"Sized {qty} units at {price} (actual cost {cost}, allocated {alloc.allocated_amount})"
                    if qty > Decimal("0")
                    else f"Capital {alloc.allocated_amount} at price {price} produced 0 units under {sz_model.value}"
                )

                sz = PositionSize(
                    sizing_id=f"size-{self._next_counter():04d}",
                    instrument_id=inst_id,
                    allocated_amount=alloc.allocated_amount,
                    unit_price=price,
                    quantity=qty,
                    actual_cost=cost,
                    sizing_model=sz_model,
                    rounding_mode=rnd_mode,
                    status=status,
                    explanation=expl,
                    as_of=as_of,
                    references=refs,
                )

                if qty > Decimal("0"):
                    sized_count += 1
                    tot_cost += cost
                    tot_qty += qty
                else:
                    zero_count += 1

            sizes.append(sz)

        summary = PositionSizingSummary(
            as_of=as_of,
            total_candidates=len(allocation_plan.allocations),
            sized_count=sized_count,
            zero_count=zero_count,
            total_allocated_capital=tot_allocated,
            total_actual_cost=tot_cost,
            total_quantity=tot_qty,
        )

        plan_id = f"szplan-{self._next_counter():04d}"
        plan_refs = SizingReferences(
            allocation_plan_id=allocation_plan.plan_id,
            portfolio_snapshot_id=allocation_plan.references.portfolio_snapshot_id,
            strategy=allocation_plan.references.strategy,
            watchlist=allocation_plan.references.watchlist,
            schedule_execution_id=allocation_plan.references.schedule_execution_id,
        )

        plan = PositionSizingPlan(
            plan_id=plan_id,
            as_of=as_of,
            allocation_plan_id=allocation_plan.plan_id,
            sizes=tuple(sizes),
            summary=summary,
            references=plan_refs,
        )

        if self._config.record_history:
            self._history = self._history.record(plan)

        return plan

    def size_amount(
        self,
        allocated_amount: Decimal,
        unit_price: Decimal,
        instrument_id: str,
        *,
        as_of: datetime,
        model: SizingModel | None = None,
        rounding: RoundingMode | None = None,
        references: SizingReferences | None = None,
    ) -> PositionSize:
        """Calculate position size for a single allocated amount and unit price."""
        if as_of.tzinfo is None:
            raise ValueError("size_amount as_of datetime must be timezone-aware")
        if unit_price <= Decimal("0.00"):
            raise SizingError(f"Unit price must be > 0, got {unit_price}")
        if allocated_amount < Decimal("0.00"):
            raise SizingError(f"Allocated amount must be >= 0, got {allocated_amount}")

        sz_model = model or self._config.default_model
        rnd_mode = rounding or self._config.default_rounding
        refs = references or SizingReferences()

        if allocated_amount == Decimal("0.00"):
            return PositionSize(
                sizing_id=f"size-{self._next_counter():04d}",
                instrument_id=instrument_id,
                allocated_amount=allocated_amount,
                unit_price=unit_price,
                quantity=Decimal("0"),
                actual_cost=Decimal("0.00"),
                sizing_model=sz_model,
                rounding_mode=rnd_mode,
                status="ZERO_ALLOCATION",
                explanation="Zero capital allocated",
                as_of=as_of,
                references=refs,
            )

        raw_qty = allocated_amount / unit_price
        qty = self._calculate_quantity(raw_qty, sz_model, rnd_mode)
        cost = _quantize(qty * unit_price)
        status = "SIZED" if qty > Decimal("0") else "ZERO_ALLOCATION"

        return PositionSize(
            sizing_id=f"size-{self._next_counter():04d}",
            instrument_id=instrument_id,
            allocated_amount=allocated_amount,
            unit_price=unit_price,
            quantity=qty,
            actual_cost=cost,
            sizing_model=sz_model,
            rounding_mode=rnd_mode,
            status=status,
            explanation=f"Sized {qty} units at {unit_price} (actual cost {cost})",
            as_of=as_of,
            references=refs,
        )

    def _calculate_quantity(
        self, raw_qty: Decimal, model: SizingModel, rounding: RoundingMode
    ) -> Decimal:
        if model == SizingModel.WHOLE_SHARE:
            if rounding == RoundingMode.ROUND_DOWN:
                return Decimal(int(raw_qty))
            else:
                return Decimal(math.ceil(raw_qty))
        else:
            prec = self._config.decimal_precision
            quantum = Decimal(10) ** -prec
            rnd = ROUND_DOWN if rounding == RoundingMode.ROUND_DOWN else ROUND_UP
            return raw_qty.quantize(quantum, rounding=rnd)

    def _next_counter(self) -> int:
        self._counter += 1
        return self._counter
