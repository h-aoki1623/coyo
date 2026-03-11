"""FastAPI application entry point."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from coyo.middleware import setup_middleware
from coyo.routers import auth, conversations, history

_is_prod = os.getenv("ENVIRONMENT") == "production"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize services on application startup."""
    from coyo.config import get_settings
    from coyo.services.firebase import initialize_firebase

    settings = get_settings()
    if settings.firebase_project_id:
        initialize_firebase(
            settings.firebase_project_id,
            service_account_path=settings.firebase_service_account_path,
        )
    yield


app = FastAPI(
    title="Coyo API",
    description="AI English conversation practice API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None if _is_prod else "/docs",
    redoc_url=None if _is_prod else "/redoc",
    openapi_url=None if _is_prod else "/openapi.json",
)

setup_middleware(app)

app.include_router(auth.router)
app.include_router(conversations.router)
app.include_router(history.router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Basic health check endpoint."""
    return {"status": "ok"}
