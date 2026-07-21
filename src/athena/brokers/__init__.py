"""Broker Abstraction Layer package (P5.5).

Defines canonical broker contracts, capability validation, and request translation.
Performs no network communication, OAuth flows, or live order placement.
"""

from athena.brokers.engine import BrokerManager
from athena.brokers.models import (
    BrokerCapabilities,
    BrokerDefinition,
    BrokerExecutionPlan,
    BrokerHistory,
    BrokerReferences,
    BrokerRequest,
    BrokerResponse,
    BrokerSummary,
)

__all__ = [
    "BrokerCapabilities",
    "BrokerDefinition",
    "BrokerExecutionPlan",
    "BrokerHistory",
    "BrokerManager",
    "BrokerReferences",
    "BrokerRequest",
    "BrokerResponse",
    "BrokerSummary",
]
