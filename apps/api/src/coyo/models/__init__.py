"""SQLAlchemy ORM models.

All models are imported here so Alembic can detect them for autogeneration.
"""

from coyo.models.base import Base
from coyo.models.conversation import Conversation
from coyo.models.conversation_summary import ConversationSummary
from coyo.models.correction import CorrectionItem, TurnCorrection
from coyo.models.topic_suggestion import TopicSuggestion, UserTopicSuggestion
from coyo.models.turn import Turn
from coyo.models.user import User, UserSettings
from coyo.models.user_interest import UserInterest
from coyo.models.user_profile_attribute import UserProfileAttribute
from coyo.models.user_profile_summary import UserProfileSummary

__all__ = [
    "Base",
    "Conversation",
    "ConversationSummary",
    "CorrectionItem",
    "TopicSuggestion",
    "Turn",
    "TurnCorrection",
    "User",
    "UserInterest",
    "UserProfileAttribute",
    "UserProfileSummary",
    "UserSettings",
    "UserTopicSuggestion",
]
