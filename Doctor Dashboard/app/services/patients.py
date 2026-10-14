"""
Data access for patients, encounters, and prescriptions.

Kept deliberately free of any FastAPI/HTTP concerns — these functions take
and return plain dicts, so they're easy to read, test, and reuse from any
route (or a future CLI/script) without dragging in Request/Response objects.
"""
import uuid
from datetime import datetime, timezone

from app.supabase_client import db


def list_patients(search: str = "", date: str = "") -> list[dict]:
    """Returns patients matching an optional name/ayush_id/phone search and/or
    an exact last_visit date, most recent visit first."""
    query = db.table("patients").select("*")

    if search:
        query = query.or_(
            f"full_name.ilike.%{search}%,ayush_id.ilike.%{search}%,phone.ilike.%{search}%,chief_complaints.ilike.%{search}%,medical_history.ilike.%{search}%"
        )
    if date:
        query = query.gte("last_visit", f"{date}T00:00:00").lte("last_visit", f"{date}T23:59:59")

    return query.order("last_visit", desc=True).execute().data


def get_patient(patient_id: str) -> dict | None:
    result = db.table("patients").select("*").eq("id", patient_id).single().execute()
    return result.data


def get_latest_encounter(patient_id: str) -> dict | None:
    result = (
        db.table("encounters")
        .select("*")
        .eq("patient_id", patient_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def get_latest_prescription(patient_id: str) -> dict | None:
    result = (
        db.table("prescriptions")
        .select("*")
        .eq("patient_id", patient_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def upsert_patient(patient_id: str | None, user_id: str, fields: dict) -> dict:
    """Creates a new patient, or updates an existing one if patient_id is given."""
    row = {**fields, "created_by": user_id, "last_visit": datetime.now(timezone.utc).isoformat()}

    if patient_id:
        result = db.table("patients").update(row).eq("id", patient_id).execute()
        return result.data[0]

    new_id = str(uuid.uuid4())
    row["id"] = new_id
    row["ayush_id"] = f"AYU-{new_id[:8].upper()}"
    result = db.table("patients").insert(row).execute()
    return result.data[0]


def insert_encounter(patient_id: str, user_id: str, fields: dict, mappings: list[dict]) -> dict:
    """Saves a clinical note as a new encounter, including the terminology
    mappings computed for it (so they're persisted, not just returned once)."""
    row = {
        "id": str(uuid.uuid4()),
        "patient_id": patient_id,
        "created_by": user_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mappings": mappings,
        **fields,
    }
    db.table("encounters").insert(row).execute()
    return row


def insert_prescription(patient_id: str, user_id: str, fields: dict) -> dict | None:
    """Saves a prescription. Returns None (and skips the insert) if every
    field was left blank, so an intake with no prescription doesn't create
    an empty row."""
    if not any(fields.values()):
        return None

    row = {
        "id": str(uuid.uuid4()),
        "patient_id": patient_id,
        "created_by": user_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        **fields,
    }
    db.table("prescriptions").insert(row).execute()
    return row
