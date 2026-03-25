"""JWT authentication middleware for the patent platform API."""
from __future__ import annotations

import os

import jwt
import structlog
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger(__name__)

# Paths that skip authentication entirely
_PUBLIC_PATHS: frozenset[str] = frozenset({"/health", "/docs", "/openapi.json"})


class AuthMiddleware(BaseHTTPMiddleware):
    """Decode a Supabase-compatible HS256 JWT and attach ``user_id`` to request state."""

    async def dispatch(self, request: Request, call_next):
        if request.url.path in _PUBLIC_PATHS:
            logger.debug("auth.skipped", path=request.url.path)
            return await call_next(request)

        auth_header: str | None = request.headers.get("Authorization")

        if not auth_header:
            logger.warning("auth.missing_header", path=request.url.path)
            return JSONResponse(
                status_code=401,
                content={"detail": "Authorization header missing"},
            )

        parts = auth_header.split(" ", 1)
        if len(parts) != 2 or parts[0] != "Bearer":
            logger.warning("auth.bad_scheme", path=request.url.path, header=auth_header[:20])
            return JSONResponse(
                status_code=401,
                content={"detail": "Authorization header must use Bearer scheme"},
            )

        token = parts[1].strip()
        if not token:
            logger.warning("auth.empty_token", path=request.url.path)
            return JSONResponse(
                status_code=401,
                content={"detail": "Authorization header missing"},
            )

        secret = os.environ.get("JWT_SECRET", "")
        try:
            payload = jwt.decode(token, secret, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            logger.warning("auth.token_expired", path=request.url.path)
            return JSONResponse(
                status_code=401,
                content={"detail": "Token expired"},
            )
        except (jwt.InvalidTokenError, Exception):
            logger.warning("auth.invalid_token", path=request.url.path)
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid token"},
            )

        user_id: str = payload.get("sub", "")
        request.state.user_id = user_id
        logger.debug("auth.ok", path=request.url.path, user_id=user_id)
        return await call_next(request)
