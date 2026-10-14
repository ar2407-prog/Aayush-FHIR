"""
Application configuration.

All values are read from environment variables (see .env.example).
Nothing here should ever be hardcoded with real secrets.
"""
import os

from dotenv import load_dotenv

load_dotenv()


def _require_env(name: str) -> str:
    """Fetches a required environment variable or fails fast with a clear error."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


class Settings:
    # Supabase project URL, e.g. https://xxxx.supabase.co
    supabase_url: str = _require_env("SUPABASE_URL")

    # Public/anon key — safe to use for Auth calls (sign up / sign in).
    supabase_anon_key: str = _require_env("SUPABASE_ANON_KEY")

    # Service role key — bypasses Row Level Security. Used ONLY for database
    # reads/writes from this server. Never send this to a browser.
    supabase_service_key: str = _require_env("SUPABASE_SERVICE_KEY")

    # Signs the session cookie. Generate a random 32+ character string for
    # production, e.g.: python -c "import secrets; print(secrets.token_hex(32))"
    session_secret: str = os.environ.get("SESSION_SECRET", "dev-only-change-me")

    # Set to False only for local HTTP development. Must be True in production
    # so the session cookie is only ever sent over HTTPS.
    session_cookie_secure: bool = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"


settings = Settings()
