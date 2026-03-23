"""FastAPI dependency injection providers."""

import asyncio
import logging
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from coyo.db import get_session_factory
from coyo.exceptions import AuthenticationError
from coyo.models.user import AuthProvider, User
from coyo.repositories.user import UserRepository
from coyo.services.firebase import FirebaseTokenPayload, verify_firebase_token

logger = logging.getLogger(__name__)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session and ensure cleanup on exit."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session


_PROVIDER_MAPPING: dict[str, AuthProvider] = {
    "password": AuthProvider.EMAIL,
    "google.com": AuthProvider.GOOGLE,
    "apple.com": AuthProvider.APPLE,
}


def _extract_bearer_token(authorization: str) -> str:
    """Extract token from 'Bearer <token>' header, or raise."""
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AuthenticationError("Invalid Authorization header format")
    return parts[1]


def map_provider(sign_in_provider: str) -> AuthProvider:
    """Map Firebase sign_in_provider to our auth_provider value."""
    mapped = _PROVIDER_MAPPING.get(sign_in_provider)
    if mapped is not None:
        return mapped
    try:
        return AuthProvider(sign_in_provider)
    except ValueError:
        logger.warning(
            "unknown_auth_provider",
            extra={"sign_in_provider": sign_in_provider, "fallback": "email"},
        )
        return AuthProvider.EMAIL


async def get_firebase_token(
    authorization: Annotated[str | None, Header()] = None,
) -> FirebaseTokenPayload | None:
    """Extract and verify Firebase ID token from Authorization header.

    Returns None if no Authorization header is present.
    Raises AuthenticationError if the header is present but invalid.
    """
    if authorization is None:
        return None

    token = _extract_bearer_token(authorization)
    return await asyncio.to_thread(verify_firebase_token, token)


async def verify_cloud_task_token(
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    """Verify OIDC token from Cloud Tasks.

    Skips verification when cloud_run_service_url is not configured (local dev).
    """
    from coyo.config import get_settings

    settings = get_settings()
    if not settings.cloud_run_service_url:
        return

    if authorization is None:
        raise AuthenticationError("Missing Authorization header")

    token = _extract_bearer_token(authorization)
    try:
        await asyncio.to_thread(
            _verify_oidc_token, token, settings.cloud_run_service_url
        )
    except AuthenticationError:
        raise
    except Exception:
        logger.warning("oidc_verification_failed", exc_info=True)
        raise AuthenticationError("Invalid OIDC token") from None


def _verify_oidc_token(token: str, audience: str) -> None:
    """Verify Google OIDC token (blocking, run in thread)."""
    from google.auth.transport.requests import Request
    from google.oauth2 import id_token

    id_token.verify_oauth2_token(token, Request(), audience)


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
    user = await repo.find_or_create_by_auth_uid(
        auth_uid=firebase_token.uid,
        email=firebase_token.email,
        display_name=firebase_token.display_name,
        auth_provider=map_provider(firebase_token.sign_in_provider),
    )
    await db.commit()
    return user
