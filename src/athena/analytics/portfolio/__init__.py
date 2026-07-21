"""Portfolio Analytics & Performance Engine package (P5.7).

Computes portfolio returns, realized/unrealized P&L, exposures, win/loss stats, and drawdowns.
Performs no investment decision making, capital allocation, or order placement.
"""

from athena.analytics.portfolio.engine import PortfolioAnalyticsEngine
from athena.analytics.portfolio.models import (
    AnalyticsSummary,
    PerformanceSnapshot,
    PortfolioAnalyticsHistory,
    PortfolioAnalyticsReferences,
    PortfolioPerformance,
    TradePerformance,
)

__all__ = [
    "AnalyticsSummary",
    "PerformanceSnapshot",
    "PortfolioAnalyticsEngine",
    "PortfolioAnalyticsHistory",
    "PortfolioAnalyticsReferences",
    "PortfolioPerformance",
    "TradePerformance",
]
