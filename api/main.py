"""Memoriant Patent Platform — FastAPI application entry-point."""
from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from api.middleware.auth import AuthMiddleware
from api.middleware.rate_limit import RateLimitMiddleware
from api.routes import analyze, config, draft, health, pipeline, search

logger = structlog.get_logger(__name__)


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
# CORS — allow web front-end origins
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Custom middleware — order: auth runs first (outermost), then rate limiting
# ---------------------------------------------------------------------------
app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuthMiddleware)

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
