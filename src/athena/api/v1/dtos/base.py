"""v1 DTO base models (P8.1).

Defines the unified response envelope and query parameter models shared
across all v1 API endpoints.

AthenaResponse[T] is the single contract for ALL successful API responses.
Pagination, sorting, and filtering models establish a consistent collection
query pattern for all future endpoint implementations.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from athena.config.models import ExportFormat

T = TypeVar("T")

class ResourceReference(BaseModel):
    """Standardized reference payload link replacing raw string identifiers."""

    model_config = ConfigDict(frozen=True)

    id: str
    resource_type: str
    display_name: str | None = None


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


F = TypeVar("F", bound=FilterParams)


@dataclass(frozen=True, slots=True)
class CollectionResult(Generic[T]):
    """Generic immutable container returned by service layer for collections."""

    items: tuple[T, ...]
    total_count: int
    page: int
    page_size: int

    @property
    def total_pages(self) -> int:
        if self.page_size <= 0:
            return 0
        return (self.total_count + self.page_size - 1) // self.page_size

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_previous(self) -> bool:
        return self.page > 1


@dataclass(frozen=True, slots=True)
class QuerySpecification(Generic[F]):
    """Bundles filters, sorting parameters, and pagination specs."""

    filters: F
    sort: SortParams
    pagination: PaginationParams


class SourceArtifactType(str, Enum):
    """Enumerates the source platform artifact categories supported for presentation export."""

    REPORT = "REPORT"
    DASHBOARD = "DASHBOARD"
    EXPLANATION = "EXPLANATION"
    TIMELINE = "TIMELINE"
    MONITORING = "MONITORING"


class ArtifactMetadataDTO(BaseModel):
    """Reusable, immutable metadata shared by all generated presentation artifacts."""

    model_config = ConfigDict(frozen=True)

    artifact_id: str
    artifact_type: SourceArtifactType
    format: ExportFormat
    filename: str
    created_at: datetime
    generated_by: str
    size_bytes: int
    content_type: str
    checksum: str | None = None


class ExportJobStatus(str, Enum):
    """Execution status states for presentation format adaptation jobs."""

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ExportJobDTO(BaseModel):
    """Job status wrapper for synchronizing asynchronous processing semantics."""

    model_config = ConfigDict(frozen=True)

    job_id: str
    status: ExportJobStatus
    created_at: datetime
    completed_at: datetime | None = None
    result_artifact_id: str | None = None
    error_message: str | None = None
