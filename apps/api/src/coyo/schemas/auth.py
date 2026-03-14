"""Schemas for authentication endpoints."""

from coyo.models.user import AuthProvider
from coyo.schemas.base import CamelModel


class SessionResponse(CamelModel):
    """Response for session creation/sync."""

    user_id: str
    email: str | None
    display_name: str | None
    auth_provider: AuthProvider
