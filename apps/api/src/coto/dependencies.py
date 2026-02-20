"""FastAPI dependency injection providers."""

from collections.abc import AsyncGenerator

from fastapi import Header
from sqlalchemy.ext.asyncio import AsyncSession

from coto.db import get_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session and ensure cleanup on exit."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session


async def get_device_id(x_device_id: str = Header(...)) -> str:
    """Extract and return the device ID from the X-Device-Id header.

    The device ID is used to identify anonymous users across sessions.
    """
    return x_device_id
