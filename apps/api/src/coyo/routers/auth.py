"""Authentication endpoints."""

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from coyo.dependencies import get_current_user
from coyo.models.user import User
from coyo.schemas.auth import SessionResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])

_URL_SCHEME = "coyo"

_APP_REDIRECT_HTML = f"""\
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Coyo</title>
<meta http-equiv="refresh" content="0;url={_URL_SCHEME}://email-verified">
</head>
<body style="font-family:system-ui,sans-serif;text-align:center;padding:60px 20px">
<p>アプリに戻ります…</p>
<p><a href="{_URL_SCHEME}://email-verified">Coyoを開く</a></p>
</body>
</html>
"""


@router.get("/app-redirect", response_class=HTMLResponse, include_in_schema=False)
async def app_redirect() -> HTMLResponse:
    """Redirect the browser to the Coyo app via custom URL scheme.

    Used as the `continueUrl` for Firebase email verification.
    After Firebase verifies the email in the browser, it redirects here,
    which in turn opens the app via the ``coyo://`` URL scheme.
    """
    return HTMLResponse(content=_APP_REDIRECT_HTML)


@router.post("/session", response_model=SessionResponse)
async def create_session(
    user: User = Depends(get_current_user),
) -> SessionResponse:
    """Create or sync a backend user record from a Firebase token.

    Called by the mobile app immediately after Firebase authentication
    so the user row exists in the database from the start.
    Idempotent: calling repeatedly for the same user is a no-op.
    """
    return SessionResponse(
        user_id=str(user.id),
        email=user.email,
        display_name=user.display_name,
        auth_provider=user.auth_provider,
    )
