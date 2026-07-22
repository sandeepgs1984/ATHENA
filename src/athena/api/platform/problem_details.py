"""RFC 9457 Problem Details error modeling (P8.5)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProblemDetail(BaseModel):
    """Unified RFC 9457 Problem Details payload schema."""

    model_config = ConfigDict(frozen=True)

    type: str = Field(..., description="URI reference identifying the problem type")
    title: str = Field(..., description="Short, human-readable summary of the problem type")
    status: int = Field(..., description="HTTP status code set by the origin server")
    detail: str = Field(..., description="Human-readable explanation specific to this occurrence")
    instance: str = Field(..., description="URI reference identifying the specific occurrence")
    request_id: str = Field(..., description="Unique request tracing ID")
    correlation_id: str = Field(..., description="Unified trace correlation ID")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
        description="Standard ISO-8601 timestamp",
    )
    invalid_params: list[dict[str, Any]] | None = Field(
        default=None,
        description="Detailed validation parameters if validation fails",
    )
    extensions: dict[str, Any] = Field(
        default_factory=dict,
        description="Custom error metadata extensions",
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert standard fields to dictionary payload for JSON responses."""
        base = {
            "type": self.type,
            "title": self.title,
            "status": self.status,
            "detail": self.detail,
            "instance": self.instance,
            "request_id": self.request_id,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp.isoformat(),
        }
        if self.invalid_params is not None:
            base["invalid_params"] = self.invalid_params
        base.update(self.extensions)
        return base
