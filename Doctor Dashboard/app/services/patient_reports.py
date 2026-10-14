"""Read-only access to the patient dashboard's Supabase data.

Tables used (created by the patient app's supabase_schema.sql):
  profiles       one row per user (role = 'patient' | 'doctor')
  reports        AI-generated structured report in `data` (jsonb)
  chat_messages  the conversation a report was generated from

This module uses the Supabase *service-role* key, which bypasses Row Level
Security. It must only ever run on the doctor backend (never in a browser), and
every route that calls it must be protected by the doctor login.
"""
from __future__ import annotations

import os
import uuid
from datetime import date, datetime
from functools import lru_cache
from typing import Any, Optional

from supabase import Client, create_client

RISK_TO_PRIORITY = {"high": "high", "moderate": "moderate", "low": "routine"}
PRIORITY_RANK = {"high": 0, "moderate": 1, "routine": 2, None: 3}
SEVERITIES = ("mild", "moderate", "severe")


# --------------------------------------------------------------------------
# Client
# --------------------------------------------------------------------------
@lru_cache(maxsize=1)
def get_client() -> Client:
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------
def compute_age(dob: Any) -> Optional[int]:
    """Whole years from a YYYY-MM-DD date of birth, computed on the server."""
    if not dob:
        return None
    try:
        born = date.fromisoformat(str(dob)[:10])
    except ValueError:
        return None
    today = date.today()
    age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    return age if 0 <= age < 150 else None


def _parse_ts(ts: Any) -> Optional[datetime]:
    if not ts:
        return None
    s = str(ts).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        try:  # older Pythons choke on odd fractional-second lengths
            return datetime.fromisoformat(s.split(".")[0])
        except ValueError:
            return None


def fmt_dt(ts: Any) -> str:
    dt = _parse_ts(ts)
    return dt.strftime("%d %b %Y, %H:%M") if dt else "—"


def fmt_date(ts: Any) -> str:
    dt = _parse_ts(ts)
    return dt.strftime("%d %b %Y") if dt else "—"


def _text(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _text_list(v: Any) -> list[str]:
    if isinstance(v, str):
        v = [v]
    if not isinstance(v, list):
        return []
    return [s for s in (_text(x) for x in v) if s]


def _bmi(height_cm: Any, weight_kg: Any) -> Optional[float]:
    try:
        h, w = float(height_cm) / 100, float(weight_kg)
        return round(w / (h * h), 1) if h > 0 and w > 0 else None
    except (TypeError, ValueError):
        return None


def _num(v: Any) -> Optional[str]:
    try:
        f = float(v)
        return str(int(f)) if f == int(f) else str(round(f, 1))
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------
# Report normalisation (the model's JSON can have empty strings / missing keys)
# --------------------------------------------------------------------------
def normalize_report(raw: Any) -> dict:
    d = raw if isinstance(raw, dict) else {}

    symptoms = []
    for s in d.get("symptoms") or []:
        if isinstance(s, str):
            s = {"name": s}
        if not isinstance(s, dict):
            continue
        name = _text(s.get("name"))
        if not name:
            continue
        sev = (_text(s.get("severity")) or "").lower()
        symptoms.append(
            {
                "name": name,
                "duration": _text(s.get("duration")),
                "severity": sev if sev in SEVERITIES else None,
                "notes": _text(s.get("notes")),
            }
        )

    risk = (_text(d.get("risk_level")) or "low").lower()
    if risk not in RISK_TO_PRIORITY:
        risk = "low"

    return {
        "title": _text(d.get("title")) or "Health report",
        "summary": _text(d.get("summary")),
        "chief_complaint": _text(d.get("chief_complaint")),
        "symptoms": symptoms,
        "considerations": _text_list(d.get("possible_considerations")),
        "red_flags": _text_list(d.get("red_flags")),
        "recommendations": _text_list(d.get("recommendations")),
        "follow_up": _text(d.get("follow_up")),
        "disclaimer": _text(d.get("disclaimer"))
        or "AI-generated summary, not a medical diagnosis.",
        "risk_level": risk,
        "priority": RISK_TO_PRIORITY[risk],
    }


def _report_view(row: dict) -> dict:
    """A report DB row -> template-ready dict."""
    r = normalize_report(row.get("data"))
    r.update(
        id=row["id"],
        session_id=row.get("session_id"),
        created_display=fmt_dt(row.get("created_at")),
        created_date=fmt_date(row.get("created_at")),
    )
    return r


def _patient_base(p: dict) -> dict:
    return {
        "id": p["id"],
        "full_name": _text(p.get("full_name")) or "Unnamed patient",
        "phone": _text(p.get("phone")),
        "gender": _text(p.get("gender")),
        "blood_group": _text(p.get("blood_group")),
        "date_of_birth": _text(p.get("date_of_birth")),
        "age": compute_age(p.get("date_of_birth")),
        "height_cm": _num(p.get("height_cm")),
        "weight_kg": _num(p.get("weight_kg")),
        "bmi": _bmi(p.get("height_cm"), p.get("weight_kg")),
        "allergies": _text(p.get("allergies")),
        "conditions": _text(p.get("conditions")),
        "medications": _text(p.get("medications")),
    }


def _valid_uuid(value: Optional[str]) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, AttributeError, TypeError):
        return False


# --------------------------------------------------------------------------
# Queries
# --------------------------------------------------------------------------
def list_patients(q: Optional[str] = None, priority: Optional[str] = None) -> dict:
    """Patients with their latest report, sorted by urgency then recency."""
    db = get_client()
    profiles = db.table("profiles").select("*").eq("role", "patient").execute().data or []
    reports = (
        db.table("reports")
        .select("id,user_id,session_id,data,created_at")
        .order("created_at", desc=True)
        .execute()
        .data
        or []
    )

    by_user: dict[str, list[dict]] = {}
    for r in reports:
        by_user.setdefault(r["user_id"], []).append(r)

    patients = []
    for p in profiles:
        base = _patient_base(p)
        rows = by_user.get(p["id"], [])
        latest = _report_view(rows[0]) if rows else None
        base.update(
            report_count=len(rows),
            latest=latest,
            priority=latest["priority"] if latest else None,
            last_report=latest["created_date"] if latest else None,
            last_report_ts=rows[0]["created_at"] if rows else "",
        )
        blob = [base["full_name"], base["phone"], base["conditions"], base["allergies"], base["medications"]]
        if latest:
            blob += [latest["title"], latest["summary"], latest["chief_complaint"]]
            blob += [s["name"] for s in latest["symptoms"]] + latest["red_flags"]
        base["search_blob"] = " ".join(str(x) for x in blob if x).lower()
        patients.append(base)

    counts = {
        "all": len(patients),
        "high": sum(1 for p in patients if p["priority"] == "high"),
        "moderate": sum(1 for p in patients if p["priority"] == "moderate"),
        "routine": sum(1 for p in patients if p["priority"] == "routine"),
    }

    if q:
        needle = q.strip().lower()
        patients = [p for p in patients if needle in p["search_blob"]]
    if priority in ("high", "moderate", "routine"):
        patients = [p for p in patients if p["priority"] == priority]

    # urgent first, then newest report first, patients without reports last
    patients.sort(key=lambda p: p["last_report_ts"], reverse=True)
    patients.sort(key=lambda p: PRIORITY_RANK[p["priority"]])
    return {"patients": patients, "counts": counts}


def get_patient_detail(patient_id: str, report_id: Optional[str] = None) -> Optional[dict]:
    """One patient, their report history, the selected report and its chat."""
    if not _valid_uuid(patient_id):
        return None
    db = get_client()
    res = db.table("profiles").select("*").eq("id", patient_id).eq("role", "patient").limit(1).execute()
    if not res.data:
        return None
    patient = _patient_base(res.data[0])

    rows = (
        db.table("reports")
        .select("id,user_id,session_id,data,created_at")
        .eq("user_id", patient_id)
        .order("created_at", desc=True)
        .execute()
        .data
        or []
    )
    history = [_report_view(r) for r in rows]
    selected = next((r for r in history if r["id"] == report_id), history[0] if history else None)

    chat: list[dict] = []
    if selected and selected.get("session_id"):
        msgs = (
            db.table("chat_messages")
            .select("role,content,created_at")
            .eq("user_id", patient_id)
            .eq("session_id", selected["session_id"])
            .order("created_at")
            .execute()
            .data
            or []
        )
        chat = [{"role": m["role"], "content": m["content"], "time": fmt_dt(m["created_at"])} for m in msgs]

    return {"patient": patient, "history": history, "report": selected, "chat": chat}
