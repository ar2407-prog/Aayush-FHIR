import json
import os
import re
import uuid
from datetime import date
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI  # OpenAI SDK works with LM Studio's local server
from pydantic import BaseModel
from supabase import Client, create_client

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]

# LM Studio local server (default port 1234). The API key can be any non-empty string.
local_llm = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")
LOCAL_MODEL = os.getenv("LOCAL_MODEL", "gemma-4")

app = FastAPI(title="Patient Dashboard API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------------------------------
# Auth & Schemas
# --------------------------------------------------------------------------


class AuthedUser:
    def __init__(self, user_id: str, email: Optional[str], db: Client):
        self.id = user_id
        self.email = email
        self.db = db


def current_user(authorization: str = Header(default="")) -> AuthedUser:
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    try:
        res = client.auth.get_user(token)
        user = res.user
    except Exception:
        raise HTTPException(401, "Invalid or expired token")
    if not user:
        raise HTTPException(401, "Invalid or expired token")
    client.postgrest.auth(token)
    return AuthedUser(user.id, user.email, client)


class ProfileIn(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    blood_group: Optional[str] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    allergies: Optional[str] = None
    conditions: Optional[str] = None
    medications: Optional[str] = None


class ChatIn(BaseModel):
    message: str
    session_id: Optional[str] = None


class ReportIn(BaseModel):
    session_id: str


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

CHAT_SYSTEM = """You are MediAssist, a caring and clear medical information assistant inside a patient dashboard.
- Use the patient's profile below to personalise answers (allergies, conditions, medications, age).
- Ask short follow-up questions about symptoms: onset, duration, severity, triggers, related symptoms.
- Give general health information and sensible self-care steps. You do NOT diagnose or prescribe.
- Flag red-flag symptoms (chest pain, trouble breathing, stroke signs, severe bleeding, suicidal thoughts) and tell the patient to seek emergency care immediately.
- Be warm, concise and use plain language. Remind the patient to confirm important decisions with a doctor when relevant.

PATIENT PROFILE:
{profile}
"""

REPORT_PROMPT = """You are a clinical documentation assistant. Based on the patient profile and the conversation,
produce a structured health report for a doctor to review. Use only information present in the
conversation/profile. When something was not discussed, use an empty string "" (or an empty list []).
Respond with ONLY the JSON object, no explanations and no markdown fences.

RED FLAGS: "red_flags" must list the patient's CURRENT, active problems that a doctor needs to see
immediately, most urgent first. Each item is one short, specific line that names the problem and
the key detail (e.g. "Chest pain radiating to left arm, started 2 hours ago", "Fever 39.5C for 3 days,
patient is on immunosuppressants"). Include any worrying symptom, dangerous combination with the
patient's conditions/medications/allergies, or sign needing urgent care. Do not list generic advice or
past, resolved issues. If there is genuinely nothing concerning, return an empty list [].
"""

# JSON schema enforced by LM Studio (response_format.type must be "json_schema" or "text").
# Unknown values are empty strings so the schema stays simple for local models.
_S = {"type": "string"}
_LIST = {"type": "array", "items": {"type": "string"}}
REPORT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": _S,
        "summary": _S,
        "patient": {
            "type": "object",
            "properties": {
                "name": _S,
                "age": _S,
                "gender": _S,
                "blood_group": _S,
                "allergies": _S,
                "conditions": _S,
                "medications": _S,
            },
            "required": ["name", "age", "gender", "blood_group", "allergies", "conditions", "medications"],
        },
        "chief_complaint": _S,
        "symptoms": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": _S,
                    "duration": _S,
                    "severity": {"type": "string", "enum": ["mild", "moderate", "severe"]},
                    "notes": _S,
                },
                "required": ["name", "duration", "severity", "notes"],
            },
        },
        "possible_considerations": _LIST,
        "risk_level": {"type": "string", "enum": ["low", "moderate", "high"]},
        "red_flags": _LIST,
        "recommendations": _LIST,
        "follow_up": _S,
        "disclaimer": _S,
    },
    "required": [
        "title", "summary", "patient", "chief_complaint", "symptoms",
        "possible_considerations", "risk_level", "red_flags",
        "recommendations", "follow_up", "disclaimer",
    ],
}


def extract_json(text: str) -> dict:
    """Parse JSON even if the model wrapped it in fences, <think> blocks or extra text."""
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.DOTALL).strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


def compute_age(dob) -> Optional[int]:
    """Age in whole years from a date_of_birth (YYYY-MM-DD), computed by the server."""
    if not dob:
        return None
    try:
        born = date.fromisoformat(str(dob)[:10])
    except ValueError:
        return None
    today = date.today()
    age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    return age if 0 <= age < 150 else None


def get_profile(u: AuthedUser) -> dict:
    res = u.db.table("profiles").select("*").eq("id", u.id).execute()
    return res.data[0] if res.data else {}


def profile_text(p: dict) -> str:
    keys = [
        "full_name", "date_of_birth", "gender", "blood_group",
        "height_cm", "weight_kg", "allergies", "conditions", "medications",
    ]
    lines = [f"- {k}: {p.get(k) or 'not provided'}" for k in keys]
    age = compute_age(p.get("date_of_birth"))
    lines.insert(2, f"- age: {age if age is not None else 'not provided'}")
    return "\n".join(lines)


def history(u: AuthedUser, session_id: str) -> list[dict]:
    res = (
        u.db.table("chat_messages")
        .select("role,content,created_at")
        .eq("user_id", u.id)
        .eq("session_id", session_id)
        .order("created_at")
        .execute()
    )
    return res.data or []


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------


@app.get("/api/config")
def public_config():
    return {"supabase_url": SUPABASE_URL, "supabase_anon_key": SUPABASE_ANON_KEY}


@app.get("/api/profile")
def read_profile(u: AuthedUser = Depends(current_user)):
    p = get_profile(u)
    p["email"] = u.email
    return p


@app.put("/api/profile")
def update_profile(body: ProfileIn, u: AuthedUser = Depends(current_user)):
    data = {k: (v if v != "" else None) for k, v in body.model_dump().items()}
    try:
        res = u.db.table("profiles").update(data).eq("id", u.id).execute()
        if not res.data:
            # Profile row missing (e.g. account created before the SQL trigger existed) -> create it.
            res = u.db.table("profiles").insert({"id": u.id, **data}).execute()
    except Exception as e:
        print("PROFILE SAVE ERROR:", repr(e))  # visible in the uvicorn terminal
        raise HTTPException(400, f"Could not save profile: {getattr(e, 'message', None) or e}")
    if not res.data:
        raise HTTPException(
            400, "Could not save profile: no row was changed (check the RLS policies on public.profiles)."
        )
    return res.data[0]


@app.get("/api/sessions")
def list_sessions(u: AuthedUser = Depends(current_user)):
    res = (
        u.db.table("chat_messages")
        .select("session_id,role,content,created_at")
        .eq("user_id", u.id)
        .order("created_at")
        .execute()
    )
    sessions: dict[str, dict] = {}
    for m in res.data or []:
        s = sessions.setdefault(
            m["session_id"],
            {"session_id": m["session_id"], "title": None, "updated_at": m["created_at"]},
        )
        if s["title"] is None and m["role"] == "user":
            s["title"] = m["content"][:48]
        s["updated_at"] = m["created_at"]
    return sorted(sessions.values(), key=lambda s: s["updated_at"], reverse=True)


@app.get("/api/chat/{session_id}")
def chat_history(session_id: str, u: AuthedUser = Depends(current_user)):
    return history(u, session_id)


@app.post("/api/chat")
def chat(body: ChatIn, u: AuthedUser = Depends(current_user)):
    text = body.message.strip()
    if not text:
        raise HTTPException(400, "Empty message")
    session_id = body.session_id or str(uuid.uuid4())

    past = history(u, session_id)
    messages = [
        {"role": "system", "content": CHAT_SYSTEM.format(profile=profile_text(get_profile(u)))}
    ]
    for m in past:
        messages.append(
            {"role": "user" if m["role"] == "user" else "assistant", "content": m["content"]}
        )
    messages.append({"role": "user", "content": text})

    try:
        resp = local_llm.chat.completions.create(
            model=LOCAL_MODEL, messages=messages, temperature=0.5
        )
        reply = (resp.choices[0].message.content or "").strip()
        reply = re.sub(r"<think>.*?</think>", "", reply, flags=re.DOTALL).strip()
        reply = reply or "Sorry, I couldn't generate a response."
    except Exception as e:
        raise HTTPException(502, f"AI service error (LM Studio): {e}")

    u.db.table("chat_messages").insert(
        [
            {"user_id": u.id, "session_id": session_id, "role": "user", "content": text},
            {"user_id": u.id, "session_id": session_id, "role": "assistant", "content": reply},
        ]
    ).execute()
    return {"session_id": session_id, "reply": reply}


@app.post("/api/report")
def generate_report(body: ReportIn, u: AuthedUser = Depends(current_user)):
    msgs = history(u, body.session_id)
    if not msgs:
        raise HTTPException(400, "This chat has no messages yet")

    transcript = "\n".join(
        f"{'PATIENT' if m['role'] == 'user' else 'ASSISTANT'}: {m['content']}" for m in msgs
    )
    prompt = (
        f"{REPORT_PROMPT}\n\nPATIENT PROFILE:\n{profile_text(get_profile(u))}\n\n"
        f"CONVERSATION:\n{transcript}"
    )
    messages = [{"role": "user", "content": prompt}]

    try:
        try:
            # Preferred: LM Studio structured output (grammar-enforced JSON).
            resp = local_llm.chat.completions.create(
                model=LOCAL_MODEL,
                messages=messages,
                temperature=0.2,
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": "health_report", "strict": True, "schema": REPORT_SCHEMA},
                },
            )
        except Exception as schema_err:
            print("json_schema call failed, retrying as plain text:", repr(schema_err))
            resp = local_llm.chat.completions.create(
                model=LOCAL_MODEL, messages=messages, temperature=0.2, response_format={"type": "text"}
            )
        data = extract_json(resp.choices[0].message.content)
        # Age is always computed from the profile's date of birth, never taken from the model.
        age = compute_age(get_profile(u).get("date_of_birth"))
        if not isinstance(data.get("patient"), dict):
            data["patient"] = {}
        data["patient"]["age"] = f"{age} years" if age is not None else ""
    except Exception as e:
        raise HTTPException(502, f"Could not generate report: {e}")

    row = (
        u.db.table("reports")
        .insert({"user_id": u.id, "session_id": body.session_id, "data": data})
        .execute()
    )
    return row.data[0]


@app.get("/api/reports")
def list_reports(u: AuthedUser = Depends(current_user)):
    res = (
        u.db.table("reports")
        .select("id,session_id,data,created_at")
        .eq("user_id", u.id)
        .order("created_at", desc=True)
        .execute()
    )
    return res.data or []


@app.get("/api/reports/{report_id}")
def get_report(report_id: str, u: AuthedUser = Depends(current_user)):
    res = u.db.table("reports").select("*").eq("id", report_id).eq("user_id", u.id).execute()
    if not res.data:
        raise HTTPException(404, "Report not found")
    return res.data[0]


# --------------------------------------------------------------------------
# Frontend (static)
# --------------------------------------------------------------------------
FRONTEND = Path(__file__).resolve().parent.parent / "frontend"


@app.get("/")
def index():
    return FileResponse(FRONTEND / "index.html")


app.mount("/static", StaticFiles(directory=FRONTEND), name="static")
