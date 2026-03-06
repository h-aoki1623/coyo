"""Middleware and exception handlers for the Coyo API."""

import uuid

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from coyo.config import get_settings
from coyo.exceptions import CoyoError


def configure_structlog() -> None:
    """Configure structlog for JSON-formatted, structured logging."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(0),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Adds a unique request ID to every request/response cycle.

    Reads X-Request-Id from the incoming request headers. If absent,
    generates a new UUID. Binds the request ID to structlog contextvars
    so all log entries within the request include it.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))

        # Bind request ID to structlog context for all downstream logging
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        return response


async def coyo_error_handler(request: Request, exc: CoyoError) -> JSONResponse:
    """Centralized handler for all CoyoError exceptions.

    Returns a consistent JSON error envelope:
    {"error": {"code": "...", "message": "..."}}
    """
    logger = structlog.get_logger()
    logger.warning(
        "application_error",
        code=exc.code,
        message=exc.message,
        status_code=exc.status_code,
        path=str(request.url),
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
            }
        },
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler for unexpected exceptions.

    Logs the full traceback but returns a generic error message
    to avoid leaking internal details to the client.
    """
    logger = structlog.get_logger()
    logger.error(
        "unhandled_error",
        exc_type=type(exc).__name__,
        exc_message=str(exc),
        path=str(request.url),
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
            }
        },
    )


def setup_middleware(app: FastAPI) -> None:
    """Register all middleware and exception handlers on the FastAPI app."""
    configure_structlog()

    # Middleware (executed in reverse registration order)
    app.add_middleware(RequestIdMiddleware)

    # CORS: restrict to configured origins
    settings = get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["X-Device-Id", "X-Request-Id", "Content-Type"],
    )

    # Exception handlers
    app.add_exception_handler(CoyoError, coyo_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_error_handler)  # type: ignore[arg-type]
