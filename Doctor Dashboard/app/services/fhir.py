"""
Terminology mapping + FHIR R4 bundle construction.

extract_terminology_mappings() is a placeholder keyword search against
ayurveda_terms — swap it for a real Supabase pgvector RPC once embeddings
are wired up (see the TODO below). build_fhir_bundle() is pure Python and
has no dependency on the web framework, so it's easy to unit test on its own.
"""
import re

from app.supabase_client import db


def extract_terminology_mappings(notes: str) -> list[dict]:
    """Finds NAMASTE/ICD-11 terminology matches for free-text clinical notes.

    TODO: replace this keyword pass with a real vector similarity search, e.g.:
        db.rpc("match_ayurveda_terms", {"query_embedding": embedding, "match_count": 5}).execute()
    """
    if not notes:
        return []

    words = re.findall(r"[a-zA-Z]{4,}", notes)
    seen_codes: set[str] = set()
    mappings: list[dict] = []

    for word in {w.lower() for w in words}:
        try:
            result = (
                db.table("ayurveda_terms")
                .select("name, namaste_code, icd11_code, description")
                .ilike("description", f"%{word}%")
                .limit(1)
                .execute()
            )
        except Exception as exc:
            print(f"Terminology lookup failed for '{word}': {exc}")
            continue

        if not result.data:
            continue

        term = result.data[0]
        code = term.get("namaste_code")
        if not code or code in seen_codes:
            continue

        seen_codes.add(code)
        mappings.append(
            {
                "extracted_term": word,
                "namaste_term": term.get("name", "Unknown"),
                "namaste_code": code,
                "icd11_code": term.get("icd11_code", ""),
                "confidence": 90,  # placeholder until real vector similarity scoring exists
            }
        )

    return mappings


def build_fhir_bundle(
    patient: dict,
    encounter: dict | None = None,
    prescription: dict | None = None,
    mappings: list[dict] | None = None,
) -> dict:
    """Builds a FHIR R4 transaction Bundle (Patient, Encounter, Condition,
    MedicationRequest) from real patient/encounter/prescription rows."""
    mappings = mappings or []
    entries = [_patient_resource(patient)]

    if encounter:
        entries.append(_encounter_resource(patient, encounter))

    for mapping in mappings:
        entries.append(_condition_resource(patient, mapping))

    if prescription and prescription.get("formulations"):
        entries.append(_medication_request_resource(patient, prescription))

    return {"resourceType": "Bundle", "type": "transaction", "entry": entries}


def _patient_resource(patient: dict) -> dict:
    resource = {
        "resourceType": "Patient",
        "id": patient.get("id"),
        "identifier": [{"system": "http://ayush.gov.in/ayush-id", "value": patient.get("ayush_id")}],
        "name": [{"text": patient.get("full_name")}],
        "gender": patient.get("gender"),
        "telecom": [{"system": "phone", "value": patient.get("phone")}] if patient.get("phone") else [],
    }
    if patient.get("age"):
        resource["extension"] = [
            {"url": "http://ayush.gov.in/fhir/StructureDefinition/age", "valueInteger": patient.get("age")}
        ]
    return {"resource": resource}


def _encounter_resource(patient: dict, encounter: dict) -> dict:
    return {
        "resource": {
            "resourceType": "Encounter",
            "status": "finished",
            "class": {"code": encounter.get("encounter_type", "ambulatory")},
            "subject": {"reference": f"Patient/{patient.get('id')}"},
            "serviceType": {"text": encounter.get("speciality", "")},
            "reasonCode": [{"text": encounter.get("notes", "")}] if encounter.get("notes") else [],
        }
    }


def _condition_resource(patient: dict, mapping: dict) -> dict:
    coding = [
        {
            "system": "http://ayush.gov.in/namaste",
            "code": mapping.get("namaste_code"),
            "display": mapping.get("namaste_term"),
        }
    ]
    if mapping.get("icd11_code"):
        coding.append({"system": "http://id.who.int/icd/release/11/mms", "code": mapping.get("icd11_code")})

    return {
        "resource": {
            "resourceType": "Condition",
            "clinicalStatus": {"coding": [{"code": "active"}]},
            "subject": {"reference": f"Patient/{patient.get('id')}"},
            "code": {"coding": coding},
        }
    }


def _medication_request_resource(patient: dict, prescription: dict) -> dict:
    return {
        "resource": {
            "resourceType": "MedicationRequest",
            "status": "active",
            "intent": "order",
            "subject": {"reference": f"Patient/{patient.get('id')}"},
            "medicationCodeableConcept": {"text": prescription.get("formulations")},
            "dosageInstruction": [{"text": prescription.get("duration", "")}],
            "note": [
                {"text": f"Pathya: {prescription.get('pathya', '')} | Apathya: {prescription.get('apathya', '')}"}
            ],
        }
    }
