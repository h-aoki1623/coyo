"""FastAPI dependency injection providers."""

import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from coto.db import get_session_factory
from coto.exceptions import ValidationError
from coto.models.user import User
from coto.repositories.user import UserRepository


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session and ensure cleanup on exit."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session


async def get_device_id(x_device_id: str = Header(...)) -> str:
    """Extract and validate the device ID from the X-Device-Id header.

    The device ID must be a valid UUID v4 string. This prevents
    abuse via crafted or excessively long header values.
    """
    try:
        uuid.UUID(x_device_id, version=4)
    except (ValueError, AttributeError) as err:
        raise ValidationError("X-Device-Id must be a valid UUID v4") from err
    return x_device_id


async def get_current_user(
    device_id: str = Depends(get_device_id),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve device ID to a User, creating one if needed.

    Uses find-or-create pattern so every device ID maps to exactly one user.
    The session is committed inside the repository if a new user is created,
    ensuring the user ID is persisted for subsequent operations.
    """
    repo = UserRepository(db)
    return await repo.find_or_create_by_device_id(device_id)
