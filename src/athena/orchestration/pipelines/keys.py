"""Typed keys for ATHENA execution pipeline artifacts and stage identifiers (P7.2).

Provides strongly typed enums replacing raw string constants in context propagation
and stage dependency definition.
"""

from enum import Enum


class ExecutionArtifactKey(str, Enum):
    """Strongly typed keys for context data artifacts passed between execution stages."""

    PORTFOLIO_SNAPSHOT = "portfolio_snapshot"
    DECISIONS = "decisions"
    CURRENT_PRICES = "current_prices"
    ALLOCATION_PLAN = "allocation_plan"
    SIZING_PLAN = "sizing_plan"
    EXECUTION_PLAN = "execution_plan"
    BROKER_PLAN = "broker_plan"
    EXECUTION_STATE = "execution_state"
    PERFORMANCE_SNAPSHOT = "performance_snapshot"


class ExecutionStageId(str, Enum):
    """Strongly typed stage identifiers for execution pipeline stages."""

    PORTFOLIO_SNAPSHOT = "stage_portfolio_snapshot"
    DECISIONS_LOAD = "stage_decisions_load"
    CAPITAL_ALLOCATION = "stage_capital_allocation"
    POSITION_SIZING = "stage_position_sizing"
    ORDER_PLANNING = "stage_order_planning"
    BROKER_TRANSLATION = "stage_broker_translation"
    ORDER_LIFECYCLE = "stage_order_lifecycle"
    PORTFOLIO_ANALYTICS = "stage_portfolio_analytics"
