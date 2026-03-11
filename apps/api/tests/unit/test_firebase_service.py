"""Unit tests for the Firebase authentication service."""

from unittest.mock import MagicMock, patch

import pytest

from coyo.exceptions import AuthenticationError
from coyo.services.firebase import FirebaseTokenPayload, verify_firebase_token


def _make_decoded_token(
    uid: str = "firebase-uid-123",
    email: str | None = "user@example.com",
    email_verified: bool = True,
    name: str | None = "Test User",
    sign_in_provider: str = "password",
) -> dict:
    """Build a decoded Firebase token dict matching firebase_admin output."""
    return {
        "uid": uid,
        "email": email,
        "email_verified": email_verified,
        "name": name,
        "firebase": {
            "sign_in_provider": sign_in_provider,
        },
    }


class TestVerifyFirebaseToken:
    """Tests for verify_firebase_token()."""

    @pytest.fixture(autouse=True)
    def _init_firebase_app(self):
        """Ensure _firebase_app is set so verify_firebase_token doesn't short-circuit."""
        with patch("coyo.services.firebase._firebase_app", new=MagicMock()):
            yield

    @pytest.mark.unit
    @patch("coyo.services.firebase.firebase_auth.verify_id_token")
    def test_valid_token_returns_payload(self, mock_verify: MagicMock):
        mock_verify.return_value = _make_decoded_token()

        result = verify_firebase_token("valid-token")

        assert isinstance(result, FirebaseTokenPayload)
        assert result.uid == "firebase-uid-123"
        assert result.email == "user@example.com"
        assert result.email_verified is True
        assert result.display_name == "Test User"
        assert result.sign_in_provider == "password"
        mock_verify.assert_called_once_with("valid-token", check_revoked=True)

    @pytest.mark.unit
    @patch("coyo.services.firebase.firebase_auth.verify_id_token")
    def test_valid_token_with_no_email(self, mock_verify: MagicMock):
        mock_verify.return_value = _make_decoded_token(
            email=None, name=None, email_verified=False
        )

        result = verify_firebase_token("token-no-email")

        assert result.email is None
        assert result.display_name is None
        assert result.email_verified is False

    @pytest.mark.unit
    @patch("coyo.services.firebase.firebase_auth.verify_id_token")
    def test_valid_token_with_no_email_verified_field(self, mock_verify: MagicMock):
        decoded = _make_decoded_token()
        del decoded["email_verified"]
        mock_verify.return_value = decoded

        result = verify_firebase_token("token")

        assert result.email_verified is False

    @pytest.mark.unit
    @patch("coyo.services.firebase.firebase_auth.verify_id_token")
    def test_expired_token_raises_authentication_error(self, mock_verify: MagicMock):
        from firebase_admin import auth as firebase_auth_module

        mock_verify.side_effect = firebase_auth_module.ExpiredIdTokenError(
            "expired", cause="test"
        )

        with pytest.raises(AuthenticationError, match="Firebase token expired"):
            verify_firebase_token("expired-token")

    @pytest.mark.unit
    @patch("coyo.services.firebase.firebase_auth.verify_id_token")
    def test_revoked_token_raises_authentication_error(self, mock_verify: MagicMock):
        from firebase_admin import auth as firebase_auth_module

        mock_verify.side_effect = firebase_auth_module.RevokedIdTokenError("revoked")

        with pytest.raises(AuthenticationError, match="Firebase token revoked"):
            verify_firebase_token("revoked-token")

    @pytest.mark.unit
    @patch("coyo.services.firebase.firebase_auth.verify_id_token")
    def test_invalid_token_raises_authentication_error(self, mock_verify: MagicMock):
        from firebase_admin import auth as firebase_auth_module

        mock_verify.side_effect = firebase_auth_module.InvalidIdTokenError(
            "invalid", cause="test"
        )

        with pytest.raises(AuthenticationError, match="Invalid Firebase token"):
            verify_firebase_token("invalid-token")

    @pytest.mark.unit
    @patch("coyo.services.firebase.firebase_auth.verify_id_token")
    def test_generic_error_raises_authentication_error(self, mock_verify: MagicMock):
        mock_verify.side_effect = RuntimeError("something went wrong")

        with pytest.raises(AuthenticationError, match="Firebase authentication failed"):
            verify_firebase_token("bad-token")

    @pytest.mark.unit
    @patch("coyo.services.firebase.firebase_auth.verify_id_token")
    def test_sign_in_provider_password(self, mock_verify: MagicMock):
        mock_verify.return_value = _make_decoded_token(sign_in_provider="password")

        result = verify_firebase_token("token")

        assert result.sign_in_provider == "password"

    @pytest.mark.unit
    @patch("coyo.services.firebase.firebase_auth.verify_id_token")
    def test_sign_in_provider_google(self, mock_verify: MagicMock):
        mock_verify.return_value = _make_decoded_token(sign_in_provider="google.com")

        result = verify_firebase_token("token")

        assert result.sign_in_provider == "google.com"

    @pytest.mark.unit
    @patch("coyo.services.firebase.firebase_auth.verify_id_token")
    def test_sign_in_provider_apple(self, mock_verify: MagicMock):
        mock_verify.return_value = _make_decoded_token(sign_in_provider="apple.com")

        result = verify_firebase_token("token")

        assert result.sign_in_provider == "apple.com"

    @pytest.mark.unit
    @patch("coyo.services.firebase.firebase_auth.verify_id_token")
    def test_missing_firebase_claims_defaults_to_unknown(self, mock_verify: MagicMock):
        decoded = _make_decoded_token()
        decoded["firebase"] = {}
        mock_verify.return_value = decoded

        result = verify_firebase_token("token")

        assert result.sign_in_provider == "unknown"

    @pytest.mark.unit
    @patch("coyo.services.firebase.firebase_auth.verify_id_token")
    def test_no_firebase_key_defaults_to_unknown(self, mock_verify: MagicMock):
        decoded = _make_decoded_token()
        del decoded["firebase"]
        mock_verify.return_value = decoded

        result = verify_firebase_token("token")

        assert result.sign_in_provider == "unknown"


class TestVerifyFirebaseTokenNotInitialized:
    """Tests for verify_firebase_token() when Firebase is not initialized."""

    @pytest.mark.unit
    def test_raises_authentication_error_when_not_initialized(self):
        with (
            patch("coyo.services.firebase._firebase_app", new=None),
            pytest.raises(AuthenticationError, match="not configured"),
        ):
            verify_firebase_token("any-token")


class TestFirebaseTokenPayload:
    """Tests for the FirebaseTokenPayload dataclass."""

    @pytest.mark.unit
    def test_payload_is_frozen(self):
        payload = FirebaseTokenPayload(
            uid="uid",
            email="a@b.com",
            email_verified=True,
            display_name="Test",
            sign_in_provider="password",
        )
        with pytest.raises(AttributeError):
            payload.uid = "new-uid"  # type: ignore[misc]
