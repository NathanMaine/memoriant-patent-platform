"""Standardised error response schema for the patent platform API."""
from __future__ import annotations

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Uniform error envelope returned for all API errors.

    Attributes:
        error:      Human-readable description of what went wrong.
        code:       Machine-readable error code (e.g. ``"AUTH_REQUIRED"``).
        request_id: Correlation ID from the originating request (may be ``None``
                    if the correlation middleware has not yet run).
        details:    Optional structured supplementary data (e.g. validation
                    field errors).
    """

    error: str
    code: str
    request_id: str | None = None
    details: dict | None = None
