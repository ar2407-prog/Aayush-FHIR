from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.dependencies import AuthRedirect
from app.routers import auth, patients, namaste, diet, patient_dashboard, patient_portal

app = FastAPI(title="AAyushFHIR")

# Signs the session cookie that stores each user's Supabase access token.
# See app/dependencies.py for how that cookie is read back on each request.
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    https_only=settings.session_cookie_secure,
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.exception_handler(AuthRedirect)
async def auth_redirect_handler(request: Request, exc: AuthRedirect):
    """Any page protected by `Depends(require_user)` raises AuthRedirect when
    there's no valid session — this sends the browser to /login instead of
    returning a raw error."""
    return RedirectResponse(url="/login", status_code=303)


app.include_router(auth.router)
app.include_router(patients.router)
app.include_router(namaste.router)
app.include_router(diet.router)
app.include_router(patient_dashboard.router)
app.include_router(patient_portal.router)


@app.get("/")
async def root():
    return RedirectResponse(url="/history")
