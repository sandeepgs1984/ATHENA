"""Starlette middleware components (P8.1).

RequestIDMiddleware: Injects a unique X-Request-ID into every request and response.
StructuredLoggingMiddleware: Logs method, path, status code, duration, and request ID.

Middleware order in create_app() (outermost to innermost):
  CORSMiddleware
  StructuredLoggingMiddleware
  RequestIDMiddleware
  -> routing
"""

from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Inject a unique request ID into every request and propagate it to the response.

    Uses the incoming X-Request-ID header if present; generates a UUID4 otherwise.
    The request ID is stored in request.state.request_id for access by handlers.
    """

    async def dispatch(self, request: Request, call_next: object) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        request.state.request_id = request_id
        response: Response = await call_next(request)  # type: ignore[operator]
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    """Log every HTTP request completion with structured fields.

    Fields: method, path, status_code, duration_ms, request_id.
    """

    async def dispatch(self, request: Request, call_next: object) -> Response:
        start = time.monotonic()
        response: Response = await call_next(request)  # type: ignore[operator]
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        request_id = getattr(request.state, "request_id", "-")
        logger.info(
            "%s %s %s %.2fms [%s]",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            request_id,
        )
        return response
