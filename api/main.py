from fastapi import FastAPI, Request
import structlog

from api.middleware.auth import AuthMiddleware
from api.middleware.rate_limit import RateLimitMiddleware

logger = structlog.get_logger(__name__)

app = FastAPI(
    title="Memoriant Patent Platform",
    version="0.1.0",
    description="Full-pipeline patent platform: idea to filing-ready draft",
)

# Middleware order: auth runs first, then rate limiting
app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuthMiddleware)

logger.info("api.startup", version="0.1.0")


@app.get("/health")
async def health():
    logger.debug("api.health_check")
    return {
        "status": "healthy",
        "version": "0.1.0",
        "services": {
            "api": "running",
        },
    }


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
