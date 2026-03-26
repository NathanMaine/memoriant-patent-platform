"""Memoriant Patent Platform — FastAPI application entry-point."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.middleware.auth import AuthMiddleware
from api.middleware.correlation import CorrelationMiddleware
from api.middleware.rate_limit import RateLimitMiddleware
from api.routes import analyze, config, draft, health, pipeline, search
from api.schemas.errors import ErrorResponse

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# CORS — allow web front-end origins (configurable via env var)
# ---------------------------------------------------------------------------
CORS_ORIGINS: list[str] = os.getenv(
    "CORS_ORIGINS", "http://localhost:3000,http://localhost:5173"
).split(",")

# Map HTTP status codes to machine-readable error codes
_STATUS_CODE_MAP: dict[int, str] = {
    400: "BAD_REQUEST",
    401: "AUTH_REQUIRED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    500: "INTERNAL_ERROR",
    503: "SERVICE_UNAVAILABLE",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("api.startup", version="0.1.0")
    yield
    logger.info("api.shutdown")


app = FastAPI(
    title="Memoriant Patent Platform",
    version="0.1.0",
    description="Full-pipeline patent platform: idea to filing-ready draft",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS middleware
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Custom middleware — innermost to outermost (starlette adds in reverse order).
# Execution order on a real request: Correlation → Auth → RateLimit
# ---------------------------------------------------------------------------
app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuthMiddleware)
app.add_middleware(CorrelationMiddleware)

# ---------------------------------------------------------------------------
# Global exception handlers — standardised error envelope
# ---------------------------------------------------------------------------


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", None)
    logger.warning("error.validation", request_id=request_id, errors=str(exc))
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            error=str(exc),
            code="VALIDATION_ERROR",
            request_id=request_id,
            details={"errors": exc.errors()},
        ).model_dump(),
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = getattr(request.state, "request_id", None)
    code = _STATUS_CODE_MAP.get(exc.status_code, "HTTP_ERROR")
    logger.warning(
        "error.http",
        request_id=request_id,
        status_code=exc.status_code,
        detail=exc.detail,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=str(exc.detail),
            code=code,
            request_id=request_id,
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", None)
    logger.error("error.unhandled", request_id=request_id, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error=str(exc),
            code="INTERNAL_ERROR",
            request_id=request_id,
        ).model_dump(),
    )


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(health.router)
app.include_router(search.router)
app.include_router(analyze.router)
app.include_router(draft.router)
app.include_router(pipeline.router)
app.include_router(config.router)

# ---------------------------------------------------------------------------
# Stub routes used by auth and rate-limit tests.
# These will be replaced by real route implementations in later tasks.
# ---------------------------------------------------------------------------


@app.get("/api/protected")
async def protected(request: Request):
    """Echo the authenticated user_id back to the caller."""
    return {"user_id": request.state.user_id}


@app.get("/api/search-stub")
async def search_stub(request: Request):
    return {"endpoint": "search", "user_id": getattr(request.state, "user_id", None)}


@app.get("/api/analyze-stub")
async def analyze_stub(request: Request):
    return {"endpoint": "analyze", "user_id": getattr(request.state, "user_id", None)}


@app.get("/api/draft-stub")
async def draft_stub(request: Request):
    return {"endpoint": "draft", "user_id": getattr(request.state, "user_id", None)}


@app.get("/api/pipeline-stub")
async def pipeline_stub(request: Request):
    return {"endpoint": "pipeline", "user_id": getattr(request.state, "user_id", None)}


@app.get("/api/config-stub")
async def config_stub(request: Request):
    return {"endpoint": "config", "user_id": getattr(request.state, "user_id", None)}
