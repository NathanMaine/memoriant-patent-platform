"""Request correlation ID middleware for the patent platform API."""
from __future__ import annotations

import uuid

import structlog
import structlog.contextvars
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = structlog.get_logger(__name__)


class CorrelationMiddleware(BaseHTTPMiddleware):
    """Attach a correlation/trace ID to every request and response.

    Precedence:
    1. Use ``X-Request-ID`` if the client provides one.
    2. Otherwise generate a new UUID4.

    The ID is stored on ``request.state.request_id`` and injected into every
    structlog log entry for the duration of the request via
    ``structlog.contextvars``.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Honour an incoming trace ID from upstream callers / load balancers.
        request_id: str = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        request.state.request_id = request_id

        # Bind to structlog context so all log entries in this request include it.
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        logger.debug("correlation.request", path=request.url.path, request_id=request_id)

        response: Response = await call_next(request)

        response.headers["X-Request-ID"] = request_id
        return response
