"""Repository for UserProfileAttribute data access."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from coyo.models.user_profile_attribute import UserProfileAttribute

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


class ProfileAttributeRepository:
    """Encapsulates database operations for the UserProfileAttribute model."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_all_for_user(
        self,
        user_id: uuid.UUID,
    ) -> list[UserProfileAttribute]:
        """Get all profile attributes for a user."""
        stmt = select(UserProfileAttribute).where(
            UserProfileAttribute.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_key(
        self,
        user_id: uuid.UUID,
        key: str,
    ) -> UserProfileAttribute | None:
        """Get a specific profile attribute by key."""
        stmt = select(UserProfileAttribute).where(
            UserProfileAttribute.user_id == user_id,
            UserProfileAttribute.key == key,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert(
        self,
        *,
        user_id: uuid.UUID,
        key: str,
        value: str,
        confidence: float,
    ) -> UserProfileAttribute:
        """Insert or update a profile attribute.

        On update, also updates the updated_at timestamp.
        """
        stmt = select(UserProfileAttribute).where(
            UserProfileAttribute.user_id == user_id,
            UserProfileAttribute.key == key,
        )
        result = await self._session.execute(stmt)
        attr = result.scalar_one_or_none()

        if attr is None:
            attr = UserProfileAttribute(
                user_id=user_id,
                key=key,
                value=value,
                confidence=confidence,
            )
            self._session.add(attr)
            try:
                await self._session.flush()
            except IntegrityError:
                # Concurrent insert race — rollback and fall through to update
                await self._session.rollback()
                result = await self._session.execute(
                    select(UserProfileAttribute).where(
                        UserProfileAttribute.user_id == user_id,
                        UserProfileAttribute.key == key,
                    )
                )
                attr = result.scalar_one()
                attr.value = value
                attr.confidence = confidence
                attr.updated_at = datetime.now(UTC)
                await self._session.flush()
        else:
            attr.value = value
            attr.confidence = confidence
            attr.updated_at = datetime.now(UTC)
            await self._session.flush()

        return attr

    async def delete(self, user_id: uuid.UUID, key: str) -> bool:
        """Delete a profile attribute. Returns True if deleted, False if not found."""
        stmt = (
            delete(UserProfileAttribute)
            .where(
                UserProfileAttribute.user_id == user_id,
                UserProfileAttribute.key == key,
            )
            .returning(UserProfileAttribute.user_id)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.scalar_one_or_none() is not None
