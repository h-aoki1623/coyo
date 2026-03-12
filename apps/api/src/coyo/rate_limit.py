"""Rate limiting configuration using slowapi.

Applies per-user rate limits to authenticated endpoints and
per-IP rate limits to public endpoints. Uses Redis as the
storage backend to share state across worker processes.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from slowapi import Limiter
from slowapi.util import get_remote_address

if TYPE_CHECKING:
    from starlette.requests import Request

# Rate limit constants
AUTH_RATE_LIMIT = "10/minute"
DEFAULT_RATE_LIMIT = "30/minute"
EXPENSIVE_RATE_LIMIT = "10/minute"


def _get_user_id_or_ip(request: Request) -> str:
    """Extract rate-limit key: user ID for authenticated requests, IP otherwise.

    Falls back to the remote IP address for unauthenticated endpoints.
    slowapi passes the Request to this function automatically.
    """
    state = getattr(request, "state", None)
    if state is not None:
        user = getattr(state, "current_user", None)
        if user is not None:
            return str(user.id)
    return get_remote_address(request)


# Read storage URI directly from environment to avoid importing Settings
# at module level (which requires all env vars to be set).
# Falls back to in-memory storage for tests and development.
_storage_uri = os.getenv("REDIS_URL", "memory://")

limiter = Limiter(
    key_func=_get_user_id_or_ip,
    storage_uri=_storage_uri,
)
