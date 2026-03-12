"""Repository for User data access."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from coyo.models.user import AuthProvider, User


class UserRepository:
    """Encapsulates database operations for the User model."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_auth_uid(self, auth_uid: str) -> User | None:
        """Find a user by their external authentication provider UID."""
        stmt = select(User).where(User.auth_uid == auth_uid)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_or_create_by_auth_uid(
        self,
        auth_uid: str,
        email: str | None,
        display_name: str | None,
        auth_provider: AuthProvider,
    ) -> User:
        """Find a user by auth_uid, or create one if not found.

        If the user exists but profile data has changed, updates the record.
        If no user exists, creates a new one.
        """
        user = await self.find_by_auth_uid(auth_uid)

        if user is not None:
            # Update profile fields if they changed
            changed = False
            if user.email != email:
                user.email = email
                changed = True
            if user.display_name != display_name:
                user.display_name = display_name
                changed = True
            if user.auth_provider != auth_provider:
                user.auth_provider = auth_provider
                changed = True
            if changed:
                await self._session.commit()
            return user

        user = User(
            auth_uid=auth_uid,
            email=email,
            display_name=display_name,
            auth_provider=auth_provider,
        )
        self._session.add(user)
        try:
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            user = await self.find_by_auth_uid(auth_uid)
            if user is None:
                raise
        return user
