"""Centralized API Platform Middleware and Request Context (P8.5)."""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from athena.api.platform.headers import (
    CORRELATION_ID_HEADER,
    REQUEST_ID_HEADER,
    inject_platform_headers,
)
from athena.api.platform.problem_details import ProblemDetail
from athena.errors import AthenaError

logger = logging.getLogger(__name__)


@dataclass
class RequestContext:
    """Thread-safe context containing request details, timing, and security principal."""

    request_id: str
    correlation_id: str
    start_time: float
    api_version: str = "v1"
    principal: Any | None = None
    execution_duration: float | None = None


class PlatformMiddleware(BaseHTTPMiddleware):
    """Unified platform middleware handling tracing, timing, logging, and exceptions."""

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        # 1. Tracing ID generation/propagation
        req_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        corr_id = request.headers.get(CORRELATION_ID_HEADER) or req_id

        # 2. Initialize RequestContext and store in request state
        start_time = time.monotonic()
        context = RequestContext(
            request_id=req_id,
            correlation_id=corr_id,
            start_time=start_time,
            api_version="v1",
        )
        request.state.request_id = req_id
        request.state.correlation_id = corr_id
        request.state.platform_context = context

        response: Response

        try:
            # 3. Call down the ASGI stack
            response = await call_next(request)
        except Exception as exc:
            # 4. Handle unexpected panic failures escaping ASGI pipeline
            duration = round((time.monotonic() - start_time) * 1000, 2)
            context.execution_duration = duration

            from athena.api.errors import exception_mapper
            prob = exception_mapper.classify(exc, str(request.url.path), req_id, corr_id)

            response = JSONResponse(
                status_code=prob.status,
                content=prob.to_dict(),
                headers={"Content-Type": "application/problem+json"},
            )

        # 5. Inject Standard Response Headers
        duration_ms = round((time.monotonic() - start_time) * 1000, 2)
        context.execution_duration = duration_ms
        inject_platform_headers(response, req_id, corr_id, context.api_version)

        # 6. Structured Request Logging
        logger.info(
            "%s %s %s %.2fms [Req: %s, Corr: %s]",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            req_id,
            corr_id,
        )

        return response
