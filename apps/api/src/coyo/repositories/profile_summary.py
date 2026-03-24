"""Repository for UserProfileSummary data access."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from coyo.models.user_profile_summary import UserProfileSummary

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


class ProfileSummaryRepository:
    """Encapsulates database operations for the UserProfileSummary model."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_for_user(
        self,
        user_id: uuid.UUID,
    ) -> UserProfileSummary | None:
        """Get the profile summary for a user."""
        stmt = select(UserProfileSummary).where(
            UserProfileSummary.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert(
        self,
        *,
        user_id: uuid.UUID,
        summary: str,
        conversation_count_at_update: int,
    ) -> UserProfileSummary:
        """Insert or update the profile summary.

        Updates updated_at on update.
        """
        stmt = select(UserProfileSummary).where(
            UserProfileSummary.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        profile_summary = result.scalar_one_or_none()

        if profile_summary is None:
            profile_summary = UserProfileSummary(
                user_id=user_id,
                summary=summary,
                conversation_count_at_update=conversation_count_at_update,
            )
            self._session.add(profile_summary)
            try:
                await self._session.flush()
            except IntegrityError:
                # Concurrent insert race — rollback and fall through to update
                await self._session.rollback()
                result = await self._session.execute(
                    select(UserProfileSummary).where(
                        UserProfileSummary.user_id == user_id,
                    )
                )
                profile_summary = result.scalar_one()
                profile_summary.summary = summary
                profile_summary.conversation_count_at_update = (
                    conversation_count_at_update
                )
                profile_summary.updated_at = datetime.now(UTC)
                await self._session.flush()
        else:
            profile_summary.summary = summary
            profile_summary.conversation_count_at_update = (
                conversation_count_at_update
            )
            profile_summary.updated_at = datetime.now(UTC)
            await self._session.flush()

        return profile_summary
