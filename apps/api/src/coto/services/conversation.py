"""Service layer for conversation lifecycle management."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from coto.exceptions import ConversationStateError, NotFoundError, ValidationError
from coto.models.conversation import Conversation
from coto.models.correction import TurnCorrection
from coto.models.turn import Turn
from coto.repositories.conversation import ConversationRepository

ALLOWED_TOPICS: frozenset[str] = frozenset(
    {"sports", "business", "technology", "politics", "entertainment"}
)


@dataclass(frozen=True)
class FeedbackStats:
    """Immutable result of feedback computation for a conversation."""

    total_turns: int
    total_corrections: int
    total_clean: int
    corrections: list[TurnCorrection]


class ConversationService:
    """Manages conversation lifecycle: start, end, resume, and retrieval."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = ConversationRepository(session)

    async def start_conversation(
        self,
        *,
        user_id: uuid.UUID,
        topic: str,
        time_limit_seconds: int = 1800,
    ) -> Conversation:
        """Start a new conversation session.

        Validates the topic, creates the conversation record,
        and returns the newly created conversation.
        """
        if topic not in ALLOWED_TOPICS:
            raise ValidationError(
                f"Invalid topic '{topic}'. Allowed: {', '.join(sorted(ALLOWED_TOPICS))}"
            )

        conversation = await self._repo.create(
            user_id=user_id,
            topic=topic,
            time_limit_seconds=time_limit_seconds,
        )
        await self._session.commit()
        return conversation

    async def get_conversation(
        self,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Conversation:
        """Retrieve a conversation by ID, scoped to the requesting user.

        Raises NotFoundError if the conversation does not exist or belongs
        to a different user (same response to prevent information disclosure).
        """
        conversation = await self._repo.get_by_id_for_user(conversation_id, user_id)
        if conversation is None:
            raise NotFoundError("Conversation", str(conversation_id))
        return conversation

    async def end_conversation(
        self,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Conversation:
        """End an active conversation and compute final metrics.

        Transitions status to 'completed', calculates duration,
        tallies corrections, and optionally computes a score.
        """
        conversation = await self._repo.get_by_id_for_user(conversation_id, user_id)
        if conversation is None:
            raise NotFoundError("Conversation", str(conversation_id))

        if conversation.status not in ("active", "paused"):
            raise ConversationStateError(
                f"Cannot end conversation in '{conversation.status}' status. "
                "Only 'active' or 'paused' conversations can be ended."
            )

        now = datetime.now(UTC)
        started_at = conversation.started_at
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=UTC)
        duration_seconds = int((now - started_at).total_seconds())

        # Count turns that have corrections
        corrections_stmt = select(Turn.id).where(
            Turn.conversation_id == conversation_id,
            Turn.correction_status == "has_corrections",
        )
        result = await self._session.execute(corrections_stmt)
        total_corrections = len(result.all())

        conversation = await self._repo.update_on_end(
            conversation_id,
            status="completed",
            ended_at=now,
            duration_seconds=duration_seconds,
            total_corrections=total_corrections,
            score=None,
        )
        await self._session.commit()
        # update_on_end already checked for None via get_by_id above
        return conversation  # type: ignore[return-value]

    async def resume_conversation(
        self,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Conversation:
        """Resume a paused conversation.

        Transitions status from 'paused' back to 'active'.
        Raises ConversationStateError if not in 'paused' status.
        """
        conversation = await self._repo.get_by_id_for_user(conversation_id, user_id)
        if conversation is None:
            raise NotFoundError("Conversation", str(conversation_id))

        if conversation.status != "paused":
            raise ConversationStateError(
                f"Cannot resume conversation in '{conversation.status}' status. "
                "Only 'paused' conversations can be resumed."
            )

        conversation = await self._repo.update_status(conversation_id, "active")
        await self._session.commit()
        return conversation  # type: ignore[return-value]

    async def get_feedback(
        self,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> list[TurnCorrection]:
        """Retrieve all corrections for turns in a conversation.

        Returns a list of TurnCorrection objects with eagerly loaded items,
        filtered to only turns that have corrections.
        """
        # Verify conversation exists and belongs to user
        conversation = await self._repo.get_by_id_for_user(conversation_id, user_id)
        if conversation is None:
            raise NotFoundError("Conversation", str(conversation_id))

        stmt = (
            select(TurnCorrection)
            .join(Turn, TurnCorrection.turn_id == Turn.id)
            .where(
                Turn.conversation_id == conversation_id,
                Turn.correction_status == "has_corrections",
            )
            .options(selectinload(TurnCorrection.items))
            .order_by(Turn.sequence)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_feedback_with_stats(
        self,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> FeedbackStats:
        """Get feedback with summary statistics for a conversation.

        Returns an immutable FeedbackStats containing total turn counts,
        corrections, and clean turns alongside the correction details.
        """
        corrections = await self.get_feedback(conversation_id, user_id)

        # Count total user turns for this conversation
        total_turns_stmt = select(func.count(Turn.id)).where(
            Turn.conversation_id == conversation_id,
            Turn.role == "user",
        )
        result = await self._session.execute(total_turns_stmt)
        total_user_turns = result.scalar() or 0

        total_corrections = len(corrections)
        total_clean = total_user_turns - total_corrections

        return FeedbackStats(
            total_turns=total_user_turns,
            total_corrections=total_corrections,
            total_clean=total_clean,
            corrections=corrections,
        )
