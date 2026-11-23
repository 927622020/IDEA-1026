from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import settings
from app.scheduler.snapshot_scheduler import create_snapshot_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    scheduler = create_snapshot_scheduler()
    scheduler.start()

    app.state.snapshot_scheduler = scheduler

    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Stockout prediction and replenishment orchestration API.",
    lifespan=lifespan,
)

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/", tags=["root"])
def root() -> dict[str, str]:
    return {"name": settings.app_name, "docs": "/docs"}


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
