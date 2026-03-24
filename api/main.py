from fastapi import FastAPI

app = FastAPI(
    title="Memoriant Patent Platform",
    version="0.1.0",
    description="Full-pipeline patent platform: idea to filing-ready draft",
)


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "version": "0.1.0",
        "services": {
            "api": "running",
        },
    }
