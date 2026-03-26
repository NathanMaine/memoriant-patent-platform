"""Per-user per-endpoint rate limiting middleware."""
from __future__ import annotations

import os
import time
from collections import defaultdict

import structlog
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from api.schemas.errors import ErrorResponse

logger = structlog.get_logger(__name__)

_WINDOW_SECONDS = 60

# Default limits (requests per minute) — overridable via env vars
_DEFAULT_LIMITS: dict[str, int] = {
    "/search": 30,
    "/analyze": 10,
    "/draft": 5,
    "/pipeline": 3,
    "/config": 10,
    "/health": 0,  # 0 means unlimited
}

_UNLIMITED_PATHS: frozenset[str] = frozenset({"/health", "/docs", "/openapi.json"})

# Env var names mapped to path prefixes
_ENV_MAP: dict[str, str] = {
    "RATE_LIMIT_SEARCH": "/search",
    "RATE_LIMIT_ANALYZE": "/analyze",
    "RATE_LIMIT_DRAFT": "/draft",
    "RATE_LIMIT_PIPELINE": "/pipeline",
    "RATE_LIMIT_CONFIG": "/config",
}


def _resolve_limits() -> dict[str, int]:
    limits = dict(_DEFAULT_LIMITS)
    for env_key, path_prefix in _ENV_MAP.items():
        val = os.environ.get(env_key)
        if val is not None:
            try:
                limits[path_prefix] = int(val)
            except ValueError:
                pass
    return limits


def _match_endpoint(path: str) -> str | None:
    """Return the first matching path prefix (longest first for precision)."""
    for prefix in sorted(_DEFAULT_LIMITS, key=len, reverse=True):
        if prefix == "/health":
            continue
        if path.startswith(prefix) or path == prefix:
            return prefix
        # Also match stub routes like /api/search-stub → /search
        stub_suffix = prefix.lstrip("/")
        if stub_suffix and (f"/{stub_suffix}-stub" in path or path.rstrip("/").endswith(stub_suffix)):
            return prefix
    return None


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiter keyed by ``user_id:endpoint``."""

    # Class-level state so it persists across requests (shared across middleware instances)
    _state: dict[str, list[float]] = defaultdict(list)

    @classmethod
    def clear_state(cls) -> None:
        """Reset all rate limit state (used in tests)."""
        cls._state.clear()

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if path in _UNLIMITED_PATHS:
            return await call_next(request)

        endpoint = _match_endpoint(path)
        if endpoint is None:
            return await call_next(request)

        limits = _resolve_limits()
        limit = limits.get(endpoint, 30)
        if limit == 0:
            # Unlimited
            return await call_next(request)

        user_id: str = getattr(request.state, "user_id", "anonymous")
        key = f"{user_id}:{path}"

        now = time.time()
        cutoff = now - _WINDOW_SECONDS

        # Evict expired timestamps
        timestamps = RateLimitMiddleware._state[key]
        timestamps[:] = [ts for ts in timestamps if ts > cutoff]

        if len(timestamps) >= limit:
            oldest = min(timestamps)
            retry_after = int(_WINDOW_SECONDS - (now - oldest)) + 1
            retry_after = max(0, retry_after)
            logger.warning(
                "rate_limit.exceeded",
                user_id=user_id,
                path=path,
                count=len(timestamps),
                limit=limit,
            )
            request_id = getattr(request.state, "request_id", None)
            return JSONResponse(
                status_code=429,
                content=ErrorResponse(
                    error=f"Rate limit exceeded. Try again in {retry_after}s.",
                    code="RATE_LIMITED",
                    request_id=request_id,
                ).model_dump(),
                headers={"Retry-After": str(retry_after)},
            )

        timestamps.append(now)
        logger.debug(
            "rate_limit.ok",
            user_id=user_id,
            path=path,
            count=len(timestamps),
            limit=limit,
        )
        return await call_next(request)
