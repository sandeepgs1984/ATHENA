"""Structured security audit logging (P8.2)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class SecurityEvent:
    """Immutable record capturing a security-sensitive event."""

    event_id: str
    ts: datetime
    event_type: str  # "LOGIN_SUCCESS", "LOGIN_FAILURE", "UNAUTHORIZED_ACCESS", etc.
    username: str | None
    request_id: str
    ip_address: str
    detail: str


class AuditSink(Protocol):
    """Protocol for recording security audit events.

    Decoupled from specific destinations (SIEM, Kafka, log systems).
    """

    def record(self, event: SecurityEvent) -> None:
        """Submit a SecurityEvent to the sink."""
        ...


class LoggingAuditSink:
    """Default AuditSink implementation writing structured events to python logger."""

    def __init__(self, logger_name: str = "athena.security.audit") -> None:
        self._logger = logging.getLogger(logger_name)

    def record(self, event: SecurityEvent) -> None:
        # Emit structured log output
        self._logger.info(
            "SecurityEvent [%s]: type=%s, user=%s, ip=%s, request=%s -> %s",
            event.event_id,
            event.event_type,
            event.username or "-",
            event.ip_address,
            event.request_id,
            event.detail,
        )
