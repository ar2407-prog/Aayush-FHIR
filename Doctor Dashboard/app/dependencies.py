"""
Auth dependencies.

Session storage: after a successful login/signup, we store the Supabase
access token and the user's email in the signed session cookie (added by
Starlette's SessionMiddleware in main.py). On every request to a protected
page, `require_user` reads that token back out and asks Supabase Auth to
verify it's still valid.

This replaces the old client-side pattern (auth.js checking localStorage and
redirecting with JavaScript) with a server-side check that runs before any
template is rendered.
"""
from fastapi import Request

from app.supabase_client import auth_client


class AuthRedirect(Exception):
    """Raised when a page requires a logged-in user but the session is missing
    or invalid. Caught by the exception handler in main.py, which sends the
    browser to /login."""


async def get_optional_user(request: Request):
    """Returns the current user if the session cookie holds a valid Supabase
    access token, otherwise None. Use this on pages that behave differently
    for logged-in vs. anonymous users but don't require a login (e.g. /login
    itself, to skip straight to /history if already signed in)."""
    token = request.session.get("access_token")
    if not token:
        return None

    try:
        response = auth_client.auth.get_user(token)
        return response.user
    except Exception:
        return None


async def require_user(request: Request):
    """FastAPI dependency for any page that must be logged in. Raises
    AuthRedirect (-> redirected to /login) if there's no valid session.

    Usage:
        @router.get("/history")
        async def history_page(request: Request, user=Depends(require_user)):
            ...
    """
    user = await get_optional_user(request)
    if user is None:
        raise AuthRedirect()
    return user
