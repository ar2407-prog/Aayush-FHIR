"""
Data access for patient kiosk intakes: Supabase Storage uploads and the
`patient_intakes` table. Kept free of HTTP concerns so app/routers/patient.py
stays focused on request handling.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from app.supabase_client import db

STORAGE_BUCKET = "patient-documents"
SIGNED_URL_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 days


def upload_document(
    intake_id: str, filename: str, content: bytes, content_type: str
) -> dict[str, Any]:
    """Uploads one legacy document to Supabase Storage and returns metadata
    to store alongside the intake record. The bucket is private; a signed
    URL is generated so staff can view the file without making the bucket
    public."""
    storage_path = f"{intake_id}/{uuid.uuid4().hex}_{filename}"

    db.storage.from_(STORAGE_BUCKET).upload(
        storage_path,
        content,
        file_options={"content-type": content_type or "application/octet-stream"},
    )

    signed = db.storage.from_(STORAGE_BUCKET).create_signed_url(
        storage_path, SIGNED_URL_TTL_SECONDS
    )
    signed_url = (
        signed.get("signedURL") or signed.get("signedUrl") or signed.get("signed_url")
    )

    return {
        "filename": filename,
        "storage_path": storage_path,
        "content_type": content_type,
        "url": signed_url,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }


def insert_intake(fields: dict[str, Any]) -> dict[str, Any]:
    row = {"created_at": datetime.now(timezone.utc).isoformat(), **fields}
    result = db.table("patient_intakes").insert(row).execute()
    return result.data[0]


def get_intake(intake_id: str) -> dict[str, Any] | None:
    result = (
        db.table("patient_intakes").select("*").eq("id", intake_id).single().execute()
    )
    return result.data


# Comprehensive bidirectional synonym dictionary mapping English terms to Ayurvedic / Hindi concepts and vice-versa
SYMPTOM_SYNONYMS: dict[str, list[str]] = {
    "fever": ["jwara", "jwar", "pyrexia", "bukhar", "taap", "temperature", "santapa", "shita jwara"],
    "cough": ["kasa", "kaas", "khasi", "coughing", "shushka kasa", "dry cough", "productive cough"],
    "cold": ["pratishyaya", "pratishyay", "sardi", "zukham", "rhinitis", "coryza", "runny nose"],
    "headache": ["shirashoola", "shirahshoola", "sir dard", "sirdard", "migraine", "ardhavabhedaka", "head pain"],
    "joint pain": ["sandhivata", "sandhishoola", "sandhi shoola", "arthritis", "osteoarthritis", "jodo ka dard", "joint stiffness", "stiffness"],
    "arthritis": ["sandhivata", "amavata", "sandhishoola", "gathiya", "joint pain"],
    "rheumatoid arthritis": ["amavata", "ama vata", "gathiya"],
    "acidity": ["amlapitta", "amla pitta", "hyperacidity", "acid reflux", "heartburn", "gerd", "gastritis", "pitta"],
    "hyperacidity": ["amlapitta", "amla pitta", "acid reflux", "heartburn", "acidity"],
    "heartburn": ["amlapitta", "hrid daha", "khatta pitta", "acidity"],
    "acid reflux": ["amlapitta", "uradhwaga amlapitta", "reflux", "gerd", "acidity"],
    "indigestion": ["mandagni", "agnimandya", "ajirna", "ajirnam", "badhazmi", "weak digestion", "dyspepsia"],
    "weak digestion": ["mandagni", "agnimandya", "slow digestion", "reduced digestive power", "indigestion"],
    "loss of appetite": ["aruchi", "agnimandya", "bhukh na lagna", "anorexia", "appetite loss"],
    "asthma": ["tamaka shwasa", "shwasa", "swas", "dama", "bronchial asthma"],
    "breathlessness": ["shwasa", "shwas", "dyspnea", "shortness of breath", "saans phulna", "difficulty breathing"],
    "shortness of breath": ["shwasa", "dyspnea", "breathlessness", "saans phulna"],
    "chest pain": ["hridshoola", "hrid shoola", "hridroga", "sineme dard", "angina"],
    "stomach pain": ["udarashoola", "udara shoola", "shoola", "pet dard", "abdominal pain", "belly pain", "cramp"],
    "abdominal pain": ["udarashoola", "udara shoola", "pet dard", "stomach pain"],
    "diarrhea": ["atisara", "atisar", "dast", "loose motions", "loose stools", "diarrhoea"],
    "loose motions": ["atisara", "dast", "loose stools", "diarrhea"],
    "dysentery": ["pravahika", "pechish", "blood in stool"],
    "vomiting": ["chardi", "chhardi", "vaman", "ulti", "emesis"],
    "nausea": ["hrillasa", "ji michlana", "mitli", "queasiness"],
    "constipation": ["vibandha", "malabaddhata", "kabz", "hard stool"],
    "skin disease": ["kushtha", "kushtha roga", "twak roga", "charmaroga", "skin allergy"],
    "skin rash": ["twak vikara", "kotha", "rash", "redness", "eruption"],
    "itching": ["kandu", "kanduti", "khujli", "pruritus"],
    "diabetes": ["prameha", "madhumeha", "sugar", "high sugar"],
    "jaundice": ["kamala", "piliya", "icterus", "yellow eyes", "liver disorder"],
    "anemia": ["pandu", "panduroga", "khoon ki kami", "anaemia", "low hemoglobin"],
    "back pain": ["katishoola", "kati shoola", "prishthashoola", "kamar dard", "backache", "lower back pain"],
    "sciatica": ["gridhrasi", "sciatica", "leg pain", "radiculopathy"],
    "neck pain": ["manyastambha", "cervical spondylosis", "gardan dard"],
    "knee pain": ["janushoola", "ghutne ka dard"],
    "body pain": ["angamarda", "sarvanga shoola", "badan dard", "body ache", "generalized pain"],
    "fatigue": ["klama", "daurbalya", "thakan", "kamzori", "tiredness", "exhaustion"],
    "weakness": ["daurbalya", "kamzori", "debility", "lethargy", "fatigue"],
    "insomnia": ["anidra", "nidranasha", "neend na aana", "sleeplessness"],
    "hypertension": ["uccha raktachapa", "raktavata", "high bp", "high blood pressure"],
    "piles": ["arsha", "arsh", "bawasir", "hemorrhoids"],
    "swelling": ["shotha", "shoth", "soojan", "edema", "oedema"],
    "edema": ["shotha", "swelling", "soojan"],
    "burning urination": ["mutrakrichhra", "mutradaha", "peshab me jalan", "dysuria", "uti"],
    "urinary infection": ["mutrakrichhra", "mutra roga", "uti", "urine infection"],
    "kidney stone": ["ashmari", "pathri", "renal calculi"],
    "paralysis": ["pakshaghata", "pakshavadha", "lakwa", "hemiplegia"],
    "fainting": ["murcha", "moorchha", "behoshi", "syncope", "loss of consciousness"],
    "dizziness": ["bhrama", "chakkar", "vertigo", "giddiness"],
}


def expand_search_terms(query: str) -> set[str]:
    """Expands an English or Ayurvedic/Hindi search query with bidirectional synonyms."""
    terms: set[str] = set()
    cleaned = query.strip().lower()
    if not cleaned:
        return terms

    terms.add(cleaned)
    for word in cleaned.split():
        if len(word) >= 2:
            terms.add(word)

    # Check bidirectional matches in SYMPTOM_SYNONYMS
    for eng_term, synonyms in SYMPTOM_SYNONYMS.items():
        all_related = set([eng_term] + [s.lower() for s in synonyms])
        # If any user search word matches the English term or any synonym
        if any(term in all_related or any(term in r for r in all_related) for term in list(terms)):
            terms.update(all_related)

    return terms


def intake_matches_search(intake: dict[str, Any], query_terms: set[str], raw_query: str) -> bool:
    """Checks if an intake matches any of the query terms or synonyms."""
    raw_query = raw_query.strip().lower()
    searchable_parts: list[str] = []

    # Patient info
    for key in ("full_name", "mobile_number", "phone", "abha_id"):
        val = intake.get(key)
        if val:
            searchable_parts.append(str(val).lower())

    # Symptoms / symptom pills
    for key in ("symptom_pills", "symptoms"):
        val = intake.get(key)
        if isinstance(val, list):
            searchable_parts.extend([str(v).lower() for v in val])
        elif isinstance(val, str) and val:
            searchable_parts.append(val.lower())

    # Clinical notes, voice transcripts, and summaries
    for key in ("symptom_notes", "voice_transcript", "extracted_medical_summary"):
        val = intake.get(key)
        if val and isinstance(val, str):
            searchable_parts.append(val.lower())

    # Priority
    if intake.get("triage_priority"):
        searchable_parts.append(str(intake["triage_priority"]).lower())

    joined_text = " ".join(searchable_parts)

    # Direct substring check
    if raw_query in joined_text:
        return True

    # Check expanded synonyms
    for term in query_terms:
        if term and term in joined_text:
            return True

    return False


def list_intakes(priority: str = "", search: str = "") -> list[dict[str, Any]]:
    """Used by the doctor dashboard to review incoming kiosk intakes, most
    recent first, optionally filtered by priority and search keyword."""
    query = db.table("patient_intakes").select("*")
    if priority:
        query = query.eq("triage_priority", priority)
    data = query.order("created_at", desc=True).execute().data or []

    if search:
        query_terms = expand_search_terms(search)
        return [
            item for item in data
            if intake_matches_search(item, query_terms, search)
        ]

    return data


def save_ai_consultation(
    intake_id: str,
    chat_history: list[dict[str, str]],
    prescription_json: dict[str, Any],
) -> dict[str, Any]:
    """Saves the AI consultation transcript and generated prescription JSON to the intake."""
    result = (
        db.table("patient_intakes")
        .update(
            {
                "ai_chat_history": chat_history,
                "prescription_json": prescription_json,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        .eq("id", intake_id)
        .execute()
    )
    return result.data[0] if result.data else None


def get_past_intakes_for_patient(
    mobile_number: str | None = None, abha_id: str | None = None
) -> list[dict[str, Any]]:
    """Fetches a patient's past intakes for medical history context (used by AI doctor)."""
    if not mobile_number and not abha_id:
        return []

    query = db.table("patient_intakes").select("*")

    if mobile_number:
        query = query.eq("mobile_number", mobile_number)
    elif abha_id:
        query = query.eq("abha_id", abha_id)

    return query.order("created_at", desc=True).limit(5).execute().data
