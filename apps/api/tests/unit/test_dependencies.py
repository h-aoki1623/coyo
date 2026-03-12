"""Unit tests for FastAPI dependency injection providers."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from coyo.dependencies import get_current_user, get_firebase_token, map_provider
from coyo.exceptions import AuthenticationError
from coyo.models.user import User
from coyo.services.firebase import FirebaseTokenPayload

# ---------------------------------------------------------------------------
# map_provider
# ---------------------------------------------------------------------------


class TestMapProvider:
    """Tests for the map_provider helper function."""

    @pytest.mark.unit
    def test_password_maps_to_email(self):
        assert map_provider("password") == "email"

    @pytest.mark.unit
    def test_google_com_maps_to_google(self):
        assert map_provider("google.com") == "google"

    @pytest.mark.unit
    def test_apple_com_maps_to_apple(self):
        assert map_provider("apple.com") == "apple"

    @pytest.mark.unit
    def test_unknown_provider_falls_back_to_email(self):
        assert map_provider("unknown") == "email"

    @pytest.mark.unit
    def test_custom_provider_falls_back_to_email(self):
        assert map_provider("github.com") == "email"


# ---------------------------------------------------------------------------
# get_firebase_token
# ---------------------------------------------------------------------------


class TestGetFirebaseToken:
    """Tests for the get_firebase_token dependency."""

    @pytest.mark.unit
    async def test_no_authorization_header_returns_none(self):
        result = await get_firebase_token(authorization=None)
        assert result is None

    @pytest.mark.unit
    async def test_valid_bearer_token_calls_verify(self):
        payload = FirebaseTokenPayload(
            uid="uid-1",
            email="a@b.com",
            email_verified=True,
            display_name="User",
            sign_in_provider="password",
        )
        with patch("coyo.dependencies.verify_firebase_token", return_value=payload) as mock_verify:
            result = await get_firebase_token(authorization="Bearer my-token-123")

        assert result == payload
        mock_verify.assert_called_once_with("my-token-123")

    @pytest.mark.unit
    async def test_invalid_header_format_no_space_raises_error(self):
        with pytest.raises(AuthenticationError, match="Invalid Authorization header format"):
            await get_firebase_token(authorization="BearerNoSpace")

    @pytest.mark.unit
    async def test_invalid_header_format_wrong_scheme_raises_error(self):
        with pytest.raises(AuthenticationError, match="Invalid Authorization header format"):
            await get_firebase_token(authorization="Basic some-creds")

    @pytest.mark.unit
    async def test_bearer_case_insensitive(self):
        payload = FirebaseTokenPayload(
            uid="uid-1",
            email="a@b.com",
            email_verified=True,
            display_name="User",
            sign_in_provider="password",
        )
        with patch("coyo.dependencies.verify_firebase_token", return_value=payload):
            result = await get_firebase_token(authorization="bearer my-token")
        assert result is not None

    @pytest.mark.unit
    async def test_empty_authorization_string_raises_error(self):
        with pytest.raises(AuthenticationError, match="Invalid Authorization header format"):
            await get_firebase_token(authorization="")


# ---------------------------------------------------------------------------
# get_current_user
# ---------------------------------------------------------------------------


class TestGetCurrentUser:
    """Tests for the get_current_user dependency."""

    @pytest.mark.unit
    async def test_firebase_token_resolves_user_via_auth_uid(self):
        firebase_token = FirebaseTokenPayload(
            uid="fb-uid-1",
            email="user@test.com",
            email_verified=True,
            display_name="Firebase User",
            sign_in_provider="password",
        )
        mock_user = MagicMock(spec=User)
        mock_db = AsyncMock(spec=AsyncSession)

        with patch("coyo.dependencies.UserRepository") as MockRepo:
            mock_repo_instance = MockRepo.return_value
            mock_repo_instance.find_or_create_by_auth_uid = AsyncMock(
                return_value=mock_user
            )
            result = await get_current_user(
                firebase_token=firebase_token,
                db=mock_db,
            )

        assert result == mock_user
        mock_repo_instance.find_or_create_by_auth_uid.assert_called_once_with(
            auth_uid="fb-uid-1",
            email="user@test.com",
            display_name="Firebase User",
            auth_provider="email",
        )

    @pytest.mark.unit
    async def test_no_firebase_token_raises_authentication_error(self):
        mock_db = AsyncMock(spec=AsyncSession)

        with pytest.raises(AuthenticationError):
            await get_current_user(
                firebase_token=None,
                db=mock_db,
            )

    @pytest.mark.unit
    async def test_google_provider_is_mapped_correctly(self):
        firebase_token = FirebaseTokenPayload(
            uid="fb-uid-1",
            email="user@test.com",
            email_verified=True,
            display_name="User",
            sign_in_provider="google.com",
        )
        mock_user = MagicMock(spec=User)
        mock_db = AsyncMock(spec=AsyncSession)

        with patch("coyo.dependencies.UserRepository") as MockRepo:
            mock_repo_instance = MockRepo.return_value
            mock_repo_instance.find_or_create_by_auth_uid = AsyncMock(
                return_value=mock_user
            )
            await get_current_user(
                firebase_token=firebase_token,
                db=mock_db,
            )

        call_kwargs = mock_repo_instance.find_or_create_by_auth_uid.call_args.kwargs
        assert call_kwargs["auth_provider"] == "google"

    @pytest.mark.unit
    async def test_apple_provider_is_mapped_correctly(self):
        firebase_token = FirebaseTokenPayload(
            uid="fb-uid-1",
            email="user@test.com",
            email_verified=True,
            display_name="User",
            sign_in_provider="apple.com",
        )
        mock_user = MagicMock(spec=User)
        mock_db = AsyncMock(spec=AsyncSession)

        with patch("coyo.dependencies.UserRepository") as MockRepo:
            mock_repo_instance = MockRepo.return_value
            mock_repo_instance.find_or_create_by_auth_uid = AsyncMock(
                return_value=mock_user
            )
            await get_current_user(
                firebase_token=firebase_token,
                db=mock_db,
            )

        call_kwargs = mock_repo_instance.find_or_create_by_auth_uid.call_args.kwargs
        assert call_kwargs["auth_provider"] == "apple"
