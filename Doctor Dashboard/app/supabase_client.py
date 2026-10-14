"""
Supabase clients.

We deliberately keep two separate clients:

- `auth_client` uses the anon/public key and is used ONLY for Auth operations
  (sign up, sign in, verifying a user's access token). This mirrors exactly
  what a public client is allowed to do.

- `db` uses the service role key and is used for ALL database reads/writes.
  It bypasses Row Level Security, which is safe here because this code only
  ever runs on the server — the browser never sees this key. Access control
  for real users is enforced by `require_user` (see dependencies.py) before
  any route touches `db`.
"""
from supabase import Client, create_client

from app.config import settings

auth_client: Client = create_client(settings.supabase_url, settings.supabase_anon_key)
db: Client = create_client(settings.supabase_url, settings.supabase_service_key)
