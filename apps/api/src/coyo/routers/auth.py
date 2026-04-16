"""Authentication endpoints."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from coyo.dependencies import get_current_user
from coyo.models.user import User
from coyo.rate_limit import AUTH_RATE_LIMIT, limiter
from coyo.schemas.auth import SessionResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])

_URL_SCHEME = "coyo"
_REDIRECT_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'",
    "X-Content-Type-Options": "nosniff",
}

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
@limiter.limit(AUTH_RATE_LIMIT)
async def app_redirect(request: Request) -> HTMLResponse:
    """Redirect the browser to the Coyo app via custom URL scheme.

    Used as the `continueUrl` for Firebase email verification.
    After Firebase verifies the email in the browser, it redirects here,
    which in turn opens the app via the ``coyo://`` URL scheme.
    """
    return HTMLResponse(
        content=_APP_REDIRECT_HTML,
        headers=_REDIRECT_HEADERS,
    )


_PASSWORD_RESET_DONE_HTML = f"""\
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Coyo</title>
<meta http-equiv="refresh" content="0;url={_URL_SCHEME}://password-reset-done">
</head>
<body style="font-family:system-ui,sans-serif;text-align:center;padding:60px 20px">
<p>アプリに戻ります…</p>
<p><a href="{_URL_SCHEME}://password-reset-done">Coyoを開く</a></p>
</body>
</html>
"""


@router.get(
    "/password-reset-redirect",
    response_class=HTMLResponse,
    include_in_schema=False,
)
@limiter.limit(AUTH_RATE_LIMIT)
async def password_reset_redirect(request: Request) -> HTMLResponse:
    """Redirect the browser to the Coyo app after a password reset.

    Used as the ``continueUrl`` for Firebase password-reset emails with
    ``handleCodeInApp=false``. After the user resets their password on
    Firebase's hosted page, Firebase redirects here, and this handler
    bounces the browser back into the app via ``coyo://password-reset-done``.
    No ``oobCode`` is expected — it was already consumed by Firebase.
    """
    return HTMLResponse(
        content=_PASSWORD_RESET_DONE_HTML,
        headers=_REDIRECT_HEADERS,
    )


@router.post("/session", response_model=SessionResponse)
@limiter.limit(AUTH_RATE_LIMIT)
async def create_session(
    request: Request,
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
