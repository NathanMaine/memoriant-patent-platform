from fastapi import FastAPI
import structlog

logger = structlog.get_logger(__name__)

app = FastAPI(
    title="Memoriant Patent Platform",
    version="0.1.0",
    description="Full-pipeline patent platform: idea to filing-ready draft",
)

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
