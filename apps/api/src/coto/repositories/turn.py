"""Repository for Turn data access."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from coto.models.turn import Turn


class TurnRepository:
    """Encapsulates database operations for the Turn model."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        conversation_id: uuid.UUID,
        role: str,
        text: str,
        sequence: int,
        audio_url: str | None = None,
        correction_status: str = "none",
    ) -> Turn:
        """Create a new turn within a conversation."""
        turn = Turn(
            conversation_id=conversation_id,
            role=role,
            text=text,
            sequence=sequence,
            audio_url=audio_url,
            correction_status=correction_status,
        )
        self._session.add(turn)
        await self._session.flush()
        return turn

    async def get_by_conversation_id(
        self,
        conversation_id: uuid.UUID,
    ) -> list[Turn]:
        """Fetch all turns for a conversation, ordered by sequence."""
        stmt = select(Turn).where(Turn.conversation_id == conversation_id).order_by(Turn.sequence)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
