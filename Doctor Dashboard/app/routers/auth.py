"""
Auth routes.

Unlike the old SPA version (where the browser called Supabase directly with
the JS SDK), sign-in/sign-up here are plain HTML form POSTs handled by this
server. We still call Supabase Auth to actually verify credentials — we're
just doing it server-side and storing the resulting session in a cookie
instead of localStorage.
"""

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.dependencies import get_optional_user
from app.supabase_client import auth_client

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    # Already signed in? Skip straight to the app instead of showing the form again.
    if await get_optional_user(request):
        return RedirectResponse(url="/history", status_code=303)

    # Properly un-indented so it runs when the user is NOT logged in
    return templates.TemplateResponse(request, "login.html", {"error": None})


@router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request, email: str = Form(...), password: str = Form(...)
):
    try:
        result = auth_client.auth.sign_in_with_password(
            {"email": email, "password": password}
        )
    except Exception:
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Invalid email or password."},
            status_code=401,
        )

    request.session["access_token"] = result.session.access_token
    request.session["refresh_token"] = result.session.refresh_token
    request.session["user_email"] = result.user.email

    return RedirectResponse(url="/history", status_code=303)


@router.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    return templates.TemplateResponse(
        request, "signup.html", {"error": None, "success": None}
    )


@router.post("/signup", response_class=HTMLResponse)
async def signup_submit(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
):
    try:
        result = auth_client.auth.sign_up(
            {
                "email": email,
                "password": password,
                "options": {"data": {"full_name": full_name}},
            }
        )
    except Exception as exc:
        return templates.TemplateResponse(
            request,
            "signup.html",
            {"error": str(exc), "success": None},
            status_code=400,
        )

    # If email confirmation is required, tell the user to check their inbox.
    if not result.session:
        return templates.TemplateResponse(
            request,
            "signup.html",
            {
                "error": None,
                "success": "Account created. Check your email to confirm before signing in.",
            },
        )

    request.session["access_token"] = result.session.access_token
    request.session["refresh_token"] = result.session.refresh_token
    request.session["user_email"] = result.user.email

    return RedirectResponse(url="/history", status_code=303)


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)
