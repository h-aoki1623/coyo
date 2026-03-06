"""Repository for User data access."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from coyo.models.user import User


class UserRepository:
    """Encapsulates database operations for the User model."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_or_create_by_device_id(self, device_id: str) -> User:
        """Find a user by device_id, or create one if not found.

        If a new user is created, the session is committed so the user ID
        is persisted and available for subsequent operations.
        """
        stmt = select(User).where(User.device_id == device_id)
        result = await self._session.execute(stmt)
        user = result.scalar_one_or_none()

        if user is not None:
            return user

        user = User(device_id=device_id)
        self._session.add(user)
        await self._session.commit()
        return user
