"""v1 DTO base models (P8.1).

Defines the unified response envelope and query parameter models shared
across all v1 API endpoints.

AthenaResponse[T] is the single contract for ALL successful API responses.
Pagination, sorting, and filtering models establish a consistent collection
query pattern for all future endpoint implementations.
"""

from __future__ import annotations

from datetime import datetime
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ResponseMeta(BaseModel):
    """Per-response metadata included in every successful API response."""

    model_config = ConfigDict(frozen=True)

    request_id: str
    api_version: str = "v1"
    as_of: datetime


class PaginationMeta(BaseModel):
    """Pagination metadata for collection responses.

    Supports both page-based (current) and cursor-based (future) pagination.
    Cursor fields are None until cursor-based pagination is introduced in P8.3+.
    No breaking contract change is required to add cursor semantics later.
    """

    model_config = ConfigDict(frozen=True)

    # Page-based (implemented in P8.1)
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool

    # Cursor-based (reserved -- not implemented in P8.1)
    next_cursor: str | None = None
    previous_cursor: str | None = None


class AthenaResponse(BaseModel, Generic[T]):
    """Single unified response envelope for ALL successful API responses.

    Single resource responses: pagination=None, links=None (omitted in JSON).
    Collection responses: pagination=PaginationMeta(...).
    Future HATEOAS: links={"self": "...", "next": "..."}.

    Replaces the previously proposed separate PagedResponse[T] model.
    """

    model_config = ConfigDict(frozen=True)

    status: Literal["success"] = "success"
    data: T
    meta: ResponseMeta
    pagination: PaginationMeta | None = None
    links: dict[str, str] | None = None      # Reserved for future HATEOAS support


class PaginationParams(BaseModel):
    """Query parameter model for paginated collection endpoints.

    Implements page/page_size today. next_cursor is reserved for future
    cursor-based pagination without requiring an API contract change.
    """

    model_config = ConfigDict(frozen=True)

    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")
    next_cursor: str | None = Field(default=None, description="Reserved for cursor pagination")


class SortParams(BaseModel):
    """Query parameter model for result ordering."""

    model_config = ConfigDict(frozen=True)

    sort_by: str | None = Field(default=None, description="Field to sort by")
    sort_dir: Literal["asc", "desc"] = Field(default="desc", description="Sort direction")


class FilterParams(BaseModel):
    """Base immutable filter model for collection endpoints.

    P8.3+ endpoints subclass this to declare endpoint-specific filter fields
    while inheriting the standard query model pattern.
    """

    model_config = ConfigDict(frozen=True)

    q: str | None = Field(default=None, description="Free-text search query")
    status: str | None = Field(default=None, description="Status filter")
    from_date: datetime | None = Field(default=None, description="Inclusive range start (tz-aware)")
    to_date: datetime | None = Field(default=None, description="Inclusive range end (tz-aware)")
