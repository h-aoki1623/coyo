"""FastAPI dependency injection providers."""

import asyncio
import logging
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from coyo.db import get_session_factory
from coyo.exceptions import AuthenticationError
from coyo.models.user import User
from coyo.repositories.user import UserRepository
from coyo.services.firebase import FirebaseTokenPayload, verify_firebase_token

logger = logging.getLogger(__name__)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session and ensure cleanup on exit."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session


_ALLOWED_PROVIDERS = frozenset({"email", "google", "apple"})

_PROVIDER_MAPPING: dict[str, str] = {
    "password": "email",
    "google.com": "google",
    "apple.com": "apple",
}


def map_provider(sign_in_provider: str) -> str:
    """Map Firebase sign_in_provider to our auth_provider value."""
    provider = _PROVIDER_MAPPING.get(sign_in_provider, sign_in_provider)
    if provider not in _ALLOWED_PROVIDERS:
        logger.warning(
            "unknown_auth_provider",
            extra={"sign_in_provider": sign_in_provider, "fallback": "email"},
        )
        return "email"
    return provider


async def get_firebase_token(
    authorization: Annotated[str | None, Header()] = None,
) -> FirebaseTokenPayload | None:
    """Extract and verify Firebase ID token from Authorization header.

    Returns None if no Authorization header is present.
    Raises AuthenticationError if the header is present but invalid.
    """
    if authorization is None:
        return None

    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AuthenticationError("Invalid Authorization header format")

    return await asyncio.to_thread(verify_firebase_token, parts[1])


async def get_current_user(
    firebase_token: FirebaseTokenPayload | None = Depends(get_firebase_token),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve user identity via Firebase token.

    Raises AuthenticationError if no valid Firebase token is provided.
    """
    if firebase_token is None:
        raise AuthenticationError()

    repo = UserRepository(db)
    return await repo.find_or_create_by_auth_uid(
        auth_uid=firebase_token.uid,
        email=firebase_token.email,
        display_name=firebase_token.display_name,
        auth_provider=map_provider(firebase_token.sign_in_provider),
    )
