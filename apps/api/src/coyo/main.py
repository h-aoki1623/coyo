"""FastAPI application entry point."""

import os

from fastapi import FastAPI

from coyo.middleware import setup_middleware
from coyo.routers import conversations, history

_is_prod = os.getenv("ENVIRONMENT") == "production"

app = FastAPI(
    title="Coyo API",
    description="AI English conversation practice API",
    version="0.1.0",
    docs_url=None if _is_prod else "/docs",
    redoc_url=None if _is_prod else "/redoc",
    openapi_url=None if _is_prod else "/openapi.json",
)

setup_middleware(app)

app.include_router(conversations.router)
app.include_router(history.router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Basic health check endpoint."""
    return {"status": "ok"}
