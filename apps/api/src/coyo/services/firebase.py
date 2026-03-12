"""Firebase Authentication service."""

from __future__ import annotations

from dataclasses import dataclass

import structlog
from firebase_admin import App as FirebaseApp
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials
from firebase_admin import initialize_app as firebase_initialize_app

from coyo.exceptions import AuthenticationError

logger = structlog.get_logger()

_firebase_app: FirebaseApp | None = None


@dataclass(frozen=True)
class FirebaseTokenPayload:
    """Verified Firebase ID token payload."""

    uid: str
    email: str | None
    email_verified: bool
    display_name: str | None
    sign_in_provider: str


def initialize_firebase(
    project_id: str | None = None,
    service_account_path: str | None = None,
) -> None:
    """Initialize Firebase Admin SDK.

    Credential resolution order:
    1. Explicit service account key file (``service_account_path``)
    2. Application Default Credentials (ADC) — automatic on Cloud Run
    """
    global _firebase_app  # noqa: PLW0603
    if _firebase_app is not None:
        return

    options: dict[str, str] = {}
    if project_id:
        options["projectId"] = project_id

    try:
        if service_account_path:
            cred = credentials.Certificate(service_account_path)
        else:
            cred = credentials.ApplicationDefault()
        _firebase_app = firebase_initialize_app(cred, options)
        logger.info("firebase_initialized", project_id=project_id)
    except Exception as err:
        logger.warning("firebase_init_skipped", reason=str(err), error_type=type(err).__name__)


def verify_firebase_token(id_token: str) -> FirebaseTokenPayload:
    """Verify a Firebase ID token and return the decoded payload.

    Raises:
        AuthenticationError: If the token is invalid, expired, or revoked.
    """
    if _firebase_app is None:
        raise AuthenticationError("Firebase authentication is not configured")

    try:
        decoded = firebase_auth.verify_id_token(id_token, check_revoked=True)
    except firebase_auth.ExpiredIdTokenError as err:
        raise AuthenticationError("Firebase token expired") from err
    except firebase_auth.RevokedIdTokenError as err:
        raise AuthenticationError("Firebase token revoked") from err
    except firebase_auth.InvalidIdTokenError as err:
        raise AuthenticationError("Invalid Firebase token") from err
    except Exception as err:
        logger.error("firebase_token_verification_failed", error=str(err))
        raise AuthenticationError("Firebase authentication failed") from err

    # Extract sign-in provider from firebase claims
    firebase_claims = decoded.get("firebase", {})
    sign_in_provider = firebase_claims.get("sign_in_provider", "unknown")

    return FirebaseTokenPayload(
        uid=decoded["uid"],
        email=decoded.get("email"),
        email_verified=decoded.get("email_verified", False),
        display_name=decoded.get("name"),
        sign_in_provider=sign_in_provider,
    )
