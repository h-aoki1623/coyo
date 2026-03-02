"""FastAPI application entry point."""

from fastapi import FastAPI

from coto.middleware import setup_middleware
from coto.routers import conversations, history

app = FastAPI(
    title="Coto API",
    description="AI English conversation practice API",
    version="0.1.0",
)

setup_middleware(app)

app.include_router(conversations.router)
app.include_router(history.router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Basic health check endpoint."""
    return {"status": "ok"}
